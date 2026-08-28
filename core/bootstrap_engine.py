from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.apps import apps
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import FieldError, ValidationError
from django.db import transaction


CREATE = "CREATE"
UPDATE = "UPDATE"
SKIP = "SKIP"
UNCHANGED = "UNCHANGED"
ERROR = "ERROR"


BOOTSTRAP_MODULES = (
    "core.bootstrap",
    "assessments.bootstrap",
    "feedback.bootstrap",
    "worldskills_forum.bootstrap",
    "behaviors.bootstrap",
    "event_countdown.bootstrap",
    "scoring.bootstrap",
)


class BootstrapConfigurationError(Exception):
    pass


class BootstrapPlanError(Exception):
    pass


@dataclass(frozen=True)
class BootstrapFieldDiff:
    field_name: str
    old_value: Any
    new_value: Any


@dataclass
class BootstrapDataset:
    label: str
    model_label: str
    key_fields: tuple[str, ...]
    collision_fields: tuple[tuple[str, ...], ...]
    records: list[dict[str, Any]]
    relations: dict[str, dict[str, Any]] = field(default_factory=dict)
    require_managed_database_keys: bool = False
    unmanaged_key_error: str = ""
    flatpage_current_site: bool = False
    default_switch_field: str | None = None
    default_switch_scope_fields: tuple[str, ...] = ()
    default_requires_active_relation: str | None = None

    @property
    def model(self):
        return apps.get_model(self.model_label)


@dataclass
class BootstrapRecordPlan:
    dataset: BootstrapDataset
    key_values: tuple[Any, ...]
    desired_values: dict[str, Any]
    action: str
    diffs: list[BootstrapFieldDiff] = field(default_factory=list)
    existing_pk: Any = None
    expected_values: dict[str, Any] = field(default_factory=dict)
    create_values: dict[str, Any] | None = None
    expected_site_bound: bool | None = None

    @property
    def identity(self) -> str:
        name = next(
            (
                self.desired_values[field_name]
                for field_name in ("name", "title", "label", "display_name")
                if field_name in self.desired_values
            ),
            None,
        )
        key = "/".join(_display_value(value) for value in self.key_values)
        return f"{key}（{name}）" if name else key


@dataclass(frozen=True)
class BootstrapIssue:
    model_label: str
    label: str
    message: str


@dataclass
class BootstrapPlan:
    force: bool
    records: list[BootstrapRecordPlan] = field(default_factory=list)
    issues: list[BootstrapIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.issues)

    @property
    def has_changes(self) -> bool:
        return any(record.action in {CREATE, UPDATE} for record in self.records)

    def counts(self) -> dict[str, int]:
        counts = {CREATE: 0, UPDATE: 0, SKIP: 0, UNCHANGED: 0, ERROR: len(self.issues)}
        for record in self.records:
            counts[record.action] += 1
        return counts


def _load_dataset_declarations() -> list[dict[str, Any]]:
    declarations = []
    for module_path in BOOTSTRAP_MODULES:
        module = __import__(module_path, fromlist=["BOOTSTRAP_DATA"])
        module_data = getattr(module, "BOOTSTRAP_DATA", None)
        if not isinstance(module_data, (list, tuple)):
            raise BootstrapConfigurationError(f"{module_path} 必须提供 BOOTSTRAP_DATA 列表。")
        declarations.extend(module_data)
    return declarations


def _normalise_dataset(declaration: dict[str, Any], *, force: bool) -> BootstrapDataset:
    required = {"label", "model", "key_fields"}
    missing = sorted(required - declaration.keys())
    if missing:
        raise BootstrapConfigurationError(
            f"Bootstrap dataset 缺少必需键：{', '.join(missing)}。"
        )

    try:
        model = apps.get_model(declaration["model"])
    except (LookupError, ValueError) as exc:
        raise BootstrapConfigurationError(
            f"Bootstrap 模型 {declaration['model']} 无法解析。"
        ) from exc

    records_source = declaration.get("records")
    if records_source is None:
        factory = declaration.get("records_factory")
        if not callable(factory):
            raise BootstrapConfigurationError(
                f"{declaration['model']} 必须声明 records 或 records_factory。"
            )
        try:
            records_source = factory(
                force=force,
                database_is_empty=not model.objects.exists(),
            )
        except (TypeError, ValueError) as exc:
            raise BootstrapConfigurationError(str(exc)) from exc

    if not isinstance(records_source, (list, tuple)) or not all(
        isinstance(record, dict) for record in records_source
    ):
        raise BootstrapConfigurationError(f"{declaration['model']} 的 records 必须是 list[dict]。")

    dataset = BootstrapDataset(
        label=str(declaration["label"]),
        model_label=str(declaration["model"]),
        key_fields=tuple(declaration["key_fields"]),
        collision_fields=tuple(
            tuple(fields) for fields in declaration.get("collision_fields", ())
        ),
        records=[dict(record) for record in records_source],
        relations=dict(declaration.get("relations", {})),
        require_managed_database_keys=bool(
            declaration.get("require_managed_database_keys", False)
        ),
        unmanaged_key_error=str(declaration.get("unmanaged_key_error", "")),
        flatpage_current_site=bool(declaration.get("flatpage_current_site", False)),
        default_switch_field=declaration.get("default_switch_field"),
        default_switch_scope_fields=tuple(
            declaration.get("default_switch_scope_fields", ())
        ),
        default_requires_active_relation=declaration.get(
            "default_requires_active_relation"
        ),
    )
    _validate_dataset_fields(dataset)
    required_default_key_factory = declaration.get("required_default_key_factory")
    if required_default_key_factory:
        required_default_key = required_default_key_factory()
        declared_keys = {
            tuple(record[field_name] for field_name in dataset.key_fields)
            for record in dataset.records
        }
        if (required_default_key,) not in declared_keys:
            raise BootstrapConfigurationError(
                f"{dataset.model_label} 的默认 key {required_default_key} 不存在。"
            )
    return dataset


def _validate_dataset_fields(dataset: BootstrapDataset) -> None:
    model_fields = {model_field.name: model_field for model_field in dataset.model._meta.fields}
    model_fields["pk"] = dataset.model._meta.pk
    for field_name in dataset.key_fields:
        if field_name not in model_fields:
            raise BootstrapConfigurationError(
                f"{dataset.model_label} 的稳定键字段 {field_name} 不存在。"
            )
    for relation_name, relation in dataset.relations.items():
        if relation_name not in model_fields or not model_fields[relation_name].is_relation:
            raise BootstrapConfigurationError(
                f"{dataset.model_label} 的关系字段 {relation_name} 不存在。"
            )
        if not relation.get("model") or not relation.get("key_fields"):
            raise BootstrapConfigurationError(
                f"{dataset.model_label}.{relation_name} 缺少自然键解析配置。"
            )
    if dataset.default_switch_field and dataset.default_switch_field not in model_fields:
        raise BootstrapConfigurationError(
            f"{dataset.model_label} 的默认项字段 {dataset.default_switch_field} 不存在。"
        )
    for field_name in dataset.default_switch_scope_fields:
        if field_name not in model_fields:
            raise BootstrapConfigurationError(
                f"{dataset.model_label} 的默认项范围字段 {field_name} 不存在。"
            )
    if (
        dataset.default_requires_active_relation
        and dataset.default_requires_active_relation not in dataset.relations
    ):
        raise BootstrapConfigurationError(
            f"{dataset.model_label} 的默认项启用关系配置无效。"
        )
    for record in dataset.records:
        unknown = set(record) - set(model_fields) - {"__create_defaults__"}
        if unknown:
            raise BootstrapConfigurationError(
                f"{dataset.model_label} 声明了不存在的字段：{', '.join(sorted(unknown))}。"
            )
        missing_keys = [field_name for field_name in dataset.key_fields if field_name not in record]
        if missing_keys:
            raise BootstrapConfigurationError(
                f"{dataset.model_label} 记录缺少稳定键：{', '.join(missing_keys)}。"
            )
        for model_field in dataset.model._meta.fields:
            if (
                model_field.name not in record
                and model_field.name not in {"id", "created_at", "updated_at", "created_by", "updated_by"}
                and not model_field.blank
                and not model_field.null
                and not model_field.has_default()
                and not getattr(model_field, "auto_created", False)
            ):
                raise BootstrapConfigurationError(
                    f"{dataset.model_label} 记录缺少必填受管字段 {model_field.name}。"
                )


def _relation_key(value: Any, relation: dict[str, Any]) -> tuple[Any, ...]:
    key_fields = tuple(relation["key_fields"])
    if len(key_fields) == 1 and not isinstance(value, (tuple, list)):
        return (value,)
    if not isinstance(value, (tuple, list)) or len(value) != len(key_fields):
        raise BootstrapConfigurationError("关系自然键的值数量与 key_fields 不一致。")
    return tuple(value)


def _relation_lookup(value: Any, relation: dict[str, Any]) -> dict[str, Any]:
    return dict(zip(relation["key_fields"], _relation_key(value, relation), strict=True))


def _resolve_relation(value: Any, relation: dict[str, Any]):
    related_model = apps.get_model(relation["model"])
    return related_model.objects.filter(**_relation_lookup(value, relation)).first()


def _convert_field_value(dataset: BootstrapDataset, field_name: str, value: Any) -> Any:
    if field_name in dataset.relations:
        return _relation_key(value, dataset.relations[field_name])
    model_field = dataset.model._meta.pk if field_name == "pk" else dataset.model._meta.get_field(field_name)
    return model_field.clean(value, None)


def _current_field_value(dataset: BootstrapDataset, instance, field_name: str) -> Any:
    if field_name in dataset.relations:
        related = getattr(instance, field_name)
        return tuple(getattr(related, key) for key in dataset.relations[field_name]["key_fields"])
    return getattr(instance, field_name)


def _record_lookup(dataset: BootstrapDataset, record: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    lookup: dict[str, Any] = {}
    errors: list[str] = []
    for field_name in dataset.key_fields:
        value = record[field_name]
        if field_name in dataset.relations:
            related = _resolve_relation(value, dataset.relations[field_name])
            if related is None:
                errors.append(
                    f"关系 {field_name} 引用的自然键 {_display_value(value)} 不存在。"
                )
                continue
            lookup[field_name] = related
        else:
            lookup[field_name] = _convert_field_value(dataset, field_name, value)
    return (lookup if not errors else None), errors


def _planned_relation_exists(
    datasets: list[BootstrapDataset], relation: dict[str, Any], value: Any
) -> bool:
    target_model = relation["model"]
    target_fields = tuple(relation["key_fields"])
    target_values = _relation_key(value, relation)
    for dataset in datasets:
        if dataset.model_label != target_model or dataset.key_fields != target_fields:
            continue
        return any(
            tuple(record[field_name] for field_name in target_fields) == target_values
            for record in dataset.records
        )
    return False


def _key_values(dataset: BootstrapDataset, record: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(_convert_field_value(dataset, field_name, record[field_name]) for field_name in dataset.key_fields)


def _record_managed_values(dataset: BootstrapDataset, record: dict[str, Any]) -> dict[str, Any]:
    return {
        field_name: _convert_field_value(dataset, field_name, value)
        for field_name, value in record.items()
        if field_name not in dataset.key_fields and field_name != "__create_defaults__"
    }


def _record_create_values(dataset: BootstrapDataset, record: dict[str, Any]) -> dict[str, Any]:
    values = {
        field_name: _convert_field_value(dataset, field_name, value)
        for field_name, value in record.items()
        if field_name != "__create_defaults__"
    }
    for field_name, value in record.get("__create_defaults__", {}).items():
        values[field_name] = _convert_field_value(dataset, field_name, value)
    return values


def _validate_declaration_duplicates(dataset: BootstrapDataset) -> list[str]:
    errors = []
    seen_keys: set[tuple[Any, ...]] = set()
    seen_collisions: list[set[tuple[Any, ...]]] = [set() for _ in dataset.collision_fields]
    for record in dataset.records:
        key = _key_values(dataset, record)
        if key in seen_keys:
            errors.append(f"声明中存在重复稳定键：{_display_value(key)}。")
        seen_keys.add(key)
        for index, collision_fields in enumerate(dataset.collision_fields):
            collision_value = tuple(
                _convert_field_value(dataset, field_name, record[field_name])
                for field_name in collision_fields
            )
            if collision_value in seen_collisions[index]:
                errors.append(
                    f"声明中存在重复冲突键 {collision_fields}：{_display_value(collision_value)}。"
                )
            seen_collisions[index].add(collision_value)
    return errors


def _database_collision(
    dataset: BootstrapDataset,
    record: dict[str, Any],
    lookup: dict[str, Any],
) -> str | None:
    model = dataset.model
    for collision_fields in dataset.collision_fields:
        collision_lookup: dict[str, Any] = {}
        for field_name in collision_fields:
            value = record[field_name]
            if field_name in dataset.relations:
                related = _resolve_relation(value, dataset.relations[field_name])
                if related is None:
                    return None
                collision_lookup[field_name] = related
            else:
                collision_lookup[field_name] = _convert_field_value(dataset, field_name, value)
        queryset = model.objects.filter(**collision_lookup).exclude(**lookup)
        if queryset.exists():
            fields_text = "/".join(collision_fields)
            value_text = "/".join(_display_value(value) for value in collision_lookup.values())
            return f"{fields_text}“{value_text}”已被其他稳定键占用，请先人工修正。"
    return None


def _build_bootstrap_plan(*, force: bool = False) -> BootstrapPlan:
    plan = BootstrapPlan(force=force)
    try:
        datasets = [
            _normalise_dataset(declaration, force=force)
            for declaration in _load_dataset_declarations()
        ]
    except BootstrapConfigurationError as exc:
        plan.issues.append(BootstrapIssue("Bootstrap", "配置", str(exc)))
        return plan

    if any(dataset.flatpage_current_site for dataset in datasets) and not Site.objects.filter(
        pk=settings.SITE_ID
    ).exists():
        plan.issues.append(
            BootstrapIssue(
                "sites.Site",
                "当前站点",
                f"settings.SITE_ID={settings.SITE_ID} 对应的 Site 不存在。",
            )
        )

    for dataset in datasets:
        for message in _validate_declaration_duplicates(dataset):
            plan.issues.append(BootstrapIssue(dataset.model_label, dataset.label, message))

        declared_keys = {_key_values(dataset, record) for record in dataset.records}
        if dataset.require_managed_database_keys:
            for instance in dataset.model.objects.all():
                database_key = tuple(getattr(instance, name) for name in dataset.key_fields)
                if database_key not in declared_keys:
                    message = dataset.unmanaged_key_error.format(
                        key="/".join(_display_value(value) for value in database_key)
                    )
                    plan.issues.append(
                        BootstrapIssue(dataset.model_label, dataset.label, message)
                    )

        for record in dataset.records:
            lookup, relation_errors = _record_lookup(dataset, record)
            for message in relation_errors:
                relation_name = next(
                    (
                        field_name
                        for field_name in dataset.key_fields
                        if field_name in dataset.relations
                        and _resolve_relation(record[field_name], dataset.relations[field_name]) is None
                    ),
                    None,
                )
                if relation_name and _planned_relation_exists(
                    datasets, dataset.relations[relation_name], record[relation_name]
                ):
                    continue
                plan.issues.append(BootstrapIssue(dataset.model_label, dataset.label, message))
            if lookup is None:
                missing_is_planned = all(
                    field_name not in dataset.relations
                    or _resolve_relation(record[field_name], dataset.relations[field_name]) is not None
                    or _planned_relation_exists(datasets, dataset.relations[field_name], record[field_name])
                    for field_name in dataset.key_fields
                )
                if not missing_is_planned:
                    continue
                lookup = None

            if lookup is not None:
                collision = _database_collision(dataset, record, lookup)
                if collision:
                    plan.issues.append(BootstrapIssue(dataset.model_label, dataset.label, collision))

            instance = dataset.model.objects.filter(**lookup).first() if lookup is not None else None
            desired_values = _record_managed_values(dataset, record)
            create_values = _record_create_values(dataset, record)
            key_values = _key_values(dataset, record)
            if instance is None:
                active_relation_name = dataset.default_requires_active_relation
                if (
                    not force
                    and active_relation_name
                    and desired_values.get(dataset.default_switch_field) is True
                ):
                    related = _resolve_relation(
                        record[active_relation_name],
                        dataset.relations[active_relation_name],
                    )
                    if related is not None and not related.is_active:
                        create_values[dataset.default_switch_field] = False
                if (
                    not force
                    and dataset.default_switch_field
                    and desired_values.get(dataset.default_switch_field) is True
                ):
                    default_lookup = {dataset.default_switch_field: True}
                    for field_name in dataset.default_switch_scope_fields:
                        value = record[field_name]
                        if field_name in dataset.relations:
                            related = _resolve_relation(value, dataset.relations[field_name])
                            if related is not None:
                                default_lookup[field_name] = related
                        else:
                            default_lookup[field_name] = _convert_field_value(
                                dataset, field_name, value
                            )
                    if dataset.model.objects.filter(**default_lookup).exists():
                        create_values[dataset.default_switch_field] = False
                plan.records.append(
                    BootstrapRecordPlan(
                        dataset=dataset,
                        key_values=key_values,
                        desired_values=desired_values,
                        action=CREATE,
                        create_values=create_values,
                    )
                )
                continue

            diffs = []
            expected_values = {}
            for field_name, desired_value in desired_values.items():
                current_value = _current_field_value(dataset, instance, field_name)
                expected_values[field_name] = current_value
                if current_value != desired_value:
                    diffs.append(BootstrapFieldDiff(field_name, current_value, desired_value))

            expected_site_bound = None
            if dataset.flatpage_current_site:
                expected_site_bound = instance.sites.filter(pk=settings.SITE_ID).exists()
                if not expected_site_bound:
                    diffs.append(BootstrapFieldDiff("sites", "未绑定当前 Site", "绑定当前 Site"))

            plan.records.append(
                BootstrapRecordPlan(
                    dataset=dataset,
                    key_values=key_values,
                    desired_values=desired_values,
                    action=(UPDATE if force else SKIP) if diffs else UNCHANGED,
                    diffs=diffs,
                    existing_pk=instance.pk,
                    expected_values=expected_values,
                    create_values=create_values,
                    expected_site_bound=expected_site_bound,
                )
            )
    return plan


def build_bootstrap_plan(*, force: bool = False) -> BootstrapPlan:
    try:
        return _build_bootstrap_plan(force=force)
    except (
        BootstrapConfigurationError,
        FieldError,
        KeyError,
        TypeError,
        ValidationError,
        ValueError,
    ) as exc:
        plan = BootstrapPlan(force=force)
        plan.issues.append(BootstrapIssue("Bootstrap", "配置", str(exc)))
        return plan


def _lookup_from_key_values(
    dataset: BootstrapDataset,
    key_values: tuple[Any, ...],
    *,
    allow_missing_relation: bool = False,
) -> dict[str, Any] | None:
    lookup = {}
    for field_name, value in zip(dataset.key_fields, key_values, strict=True):
        if field_name in dataset.relations:
            related = _resolve_relation(value, dataset.relations[field_name])
            if related is None:
                if allow_missing_relation:
                    return None
                raise BootstrapPlanError(
                    f"{dataset.model_label} 的关系 {field_name} 在执行前已不存在。"
                )
            lookup[field_name] = related
        else:
            lookup[field_name] = value
    return lookup


def _assert_plan_is_fresh(plan: BootstrapPlan) -> None:
    for record in plan.records:
        force_record_must_stay_current = plan.force and record.existing_pk is not None
        if record.action not in {CREATE, UPDATE} and not force_record_must_stay_current:
            continue
        lookup = _lookup_from_key_values(
            record.dataset,
            record.key_values,
            allow_missing_relation=record.action == CREATE,
        )
        instance = (
            record.dataset.model.objects.filter(**lookup).first()
            if lookup is not None
            else None
        )
        if record.action == CREATE:
            if instance is not None:
                raise BootstrapPlanError(
                    f"{record.dataset.model_label} {record.identity} 在预览后已被创建。"
                )
            if lookup is not None:
                collision = _database_collision(
                    record.dataset,
                    record.create_values or {},
                    lookup,
                )
                if collision:
                    raise BootstrapPlanError(
                        f"{record.dataset.model_label} {record.identity} 在预览后出现冲突：{collision}"
                    )
            continue
        if instance is None or instance.pk != record.existing_pk:
            raise BootstrapPlanError(
                f"{record.dataset.model_label} {record.identity} 在预览后已变化。"
            )
        for field_name, expected_value in record.expected_values.items():
            if _current_field_value(record.dataset, instance, field_name) != expected_value:
                raise BootstrapPlanError(
                    f"{record.dataset.model_label} {record.identity} 的 {field_name} 在预览后已变化。"
                )
        if record.dataset.flatpage_current_site:
            site_bound = instance.sites.filter(pk=settings.SITE_ID).exists()
            if site_bound != record.expected_site_bound:
                raise BootstrapPlanError(
                    f"{record.dataset.model_label} {record.identity} 的 Site 关系在预览后已变化。"
                )
        collision = _database_collision(
            record.dataset,
            record.create_values or {},
            lookup,
        )
        if collision:
            raise BootstrapPlanError(
                f"{record.dataset.model_label} {record.identity} 在预览后出现冲突：{collision}"
            )


def _model_values(dataset: BootstrapDataset, values: dict[str, Any]) -> dict[str, Any]:
    resolved = {}
    for field_name, value in values.items():
        if field_name in dataset.relations:
            related = _resolve_relation(value, dataset.relations[field_name])
            if related is None:
                raise BootstrapPlanError(
                    f"{dataset.model_label} 的关系 {field_name} 无法在执行时解析。"
                )
            resolved[field_name] = related
        else:
            resolved[field_name] = value
    return resolved


def _prepare_default_switches(plan: BootstrapPlan) -> None:
    if not plan.force:
        return
    datasets: dict[int, BootstrapDataset] = {}
    for record in plan.records:
        if record.action in {CREATE, UPDATE} and record.dataset.default_switch_field:
            datasets[id(record.dataset)] = record.dataset
    for dataset in datasets.values():
        field_name = dataset.default_switch_field
        false_pks = [
            record.existing_pk
            for record in plan.records
            if record.dataset is dataset
            and record.existing_pk is not None
            and record.desired_values.get(field_name) is False
        ]
        if false_pks:
            dataset.model.objects.filter(pk__in=false_pks).update(**{field_name: False})


def apply_bootstrap_plan(plan: BootstrapPlan) -> dict[str, int]:
    if plan.has_errors:
        raise BootstrapPlanError("Bootstrap 预检存在错误，不能执行。")
    with transaction.atomic():
        _assert_plan_is_fresh(plan)
        _prepare_default_switches(plan)
        for record in plan.records:
            if record.action == CREATE:
                values = _model_values(record.dataset, record.create_values or {})
                instance = record.dataset.model(**values)
                instance.full_clean()
                instance.save()
                if record.dataset.flatpage_current_site:
                    instance.sites.add(Site.objects.get(pk=settings.SITE_ID))
            elif record.action == UPDATE:
                lookup = _lookup_from_key_values(record.dataset, record.key_values)
                instance = record.dataset.model.objects.get(**lookup)
                for field_name, value in _model_values(
                    record.dataset, record.desired_values
                ).items():
                    setattr(instance, field_name, value)
                instance.full_clean()
                instance.save(update_fields=[*record.desired_values, "updated_at"] if hasattr(instance, "updated_at") else list(record.desired_values))
                if record.dataset.flatpage_current_site and not record.expected_site_bound:
                    instance.sites.add(Site.objects.get(pk=settings.SITE_ID))
    return plan.counts()


def bootstrap_defaults() -> dict[str, int]:
    """为测试和内部显式调用执行普通 Bootstrap；生产入口仍是 management command。"""
    plan = build_bootstrap_plan()
    if plan.has_errors:
        messages = "; ".join(issue.message for issue in plan.issues)
        raise BootstrapPlanError(messages)
    return apply_bootstrap_plan(plan)


def _display_value(value: Any) -> str:
    if isinstance(value, tuple):
        return "/".join(_display_value(item) for item in value)
    if value is True:
        return "是"
    if value is False:
        return "否"
    if value is None:
        return "空"
    return str(value)


def render_bootstrap_plan(plan: BootstrapPlan) -> str:
    lines = [
        "TMS 默认业务数据预览",
        f"模式：{'强制覆盖' if plan.force else '普通'}",
    ]
    if plan.force:
        lines.append("强制覆盖模式：将覆盖 Bootstrap 已声明记录的受管字段；不会删除额外数据库数据。")
    lines.extend(["=" * 60, ""])

    current_dataset = None
    symbols = {CREATE: "+", UPDATE: "~", SKIP: "~", UNCHANGED: "="}
    for record in plan.records:
        if record.dataset is not current_dataset:
            current_dataset = record.dataset
            lines.extend(
                [f"[{record.dataset.model_label}] {record.dataset.label}", ""]
            )
        lines.append(f"{symbols[record.action]} {record.action:<9} {record.identity}")
        for diff in record.diffs:
            lines.append(
                f"    {diff.field_name}: {_display_value(diff.old_value)} -> {_display_value(diff.new_value)}"
            )
        lines.append("")

    for issue in plan.issues:
        lines.extend(
            [f"[{issue.model_label}] {issue.label}", "", f"! ERROR     {issue.message}", ""]
        )

    counts = plan.counts()
    lines.extend(
        [
            "-" * 60,
            " ".join(
                f"{action}: {counts[action]}"
                for action in (CREATE, UPDATE, SKIP, UNCHANGED, ERROR)
            ),
        ]
    )
    return "\n".join(lines)
