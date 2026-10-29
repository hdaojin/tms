"""角色的 Bootstrap 预检、差异和落库，纳入主 Bootstrap 的单一事务。"""

from dataclasses import dataclass

from django.contrib.auth.models import Group

from accounts.models import GroupProfile
from accounts.services.groups import ensure_group_profile
from accounts.services.permission_assignments import sync_group_permission_assignments
from core.permissions import get_permissions_for_bundle_codes, normalize_permission_bundle_codes


@dataclass
class RolePlan:
    values: dict
    action: str
    expected: dict | None
    permission_labels: tuple[str, ...]


def _snapshot(profile):
    return {
        "pk": profile.pk,
        "group_id": profile.group_id,
        "name": profile.group.name,
        "description": profile.description,
        "bundles": profile.selected_permission_bundles,
        "explicit": sorted(profile.explicit_permissions.values_list("pk", flat=True)),
        "permissions": sorted(profile.group.permissions.values_list("pk", flat=True)),
        "members": sorted(profile.group.user_set.values_list("pk", flat=True)),
        "domains": sorted(profile.group.technical_domain_scopes.values_list("technical_domain_id", flat=True)),
    }


def build_role_plans(*, force):
    from accounts.bootstrap import DEFAULT_ROLES

    plans = []
    seen_codes, seen_names = set(), set()
    for source in DEFAULT_ROLES:
        values = {**source, "bundles": normalize_permission_bundle_codes(source["bundles"])}
        if values["codename"] in seen_codes or values["name"] in seen_names:
            raise ValueError("默认角色声明存在重复标识或名称。")
        seen_codes.add(values["codename"])
        seen_names.add(values["name"])
        # 只构造未保存对象以验证稳定标识；此阶段不得补建 Profile。
        GroupProfile(codename=values["codename"]).clean_fields(exclude=["group"])
        permissions = get_permissions_for_bundle_codes(values["bundles"])
        labels = tuple(sorted(f"{p.content_type.app_label}.{p.codename}" for p in permissions))
        profile = GroupProfile.objects.select_related("group").filter(codename=values["codename"]).first()
        collision = Group.objects.filter(name=values["name"])
        if profile:
            collision = collision.exclude(pk=profile.group_id)
        if collision.exists():
            raise ValueError(f"默认角色“{values['name']}”名称已被其他稳定标识占用，请先人工处理。")
        expected = _snapshot(profile) if profile else None
        different = expected is not None and (
            any(expected[key] != values[key] for key in ("name", "description", "bundles"))
            or (
                force
                and expected["permissions"]
                != sorted(set(permissions.values_list("pk", flat=True)) | set(expected["explicit"]))
            )
        )
        action = "CREATE" if profile is None else ("UPDATE" if force else "SKIP") if different else "UNCHANGED"
        plans.append(RolePlan(values, action, expected, labels))
    return plans


def assert_role_plans_fresh(plans):
    for plan in plans:
        profile = (
            GroupProfile.objects.select_for_update()
            .select_related("group")
            .filter(codename=plan.values["codename"])
            .first()
        )
        if (_snapshot(profile) if profile else None) != plan.expected:
            raise ValueError(f"默认角色 {plan.values['codename']} 在预览后发生变化，请重新预览。")
        collision = Group.objects.filter(name=plan.values["name"])
        if profile:
            collision = collision.exclude(pk=profile.group_id)
        if collision.exists():
            raise ValueError(f"默认角色“{plan.values['name']}”在预览后出现名称冲突。")


def apply_role_plans(plans):
    for plan in plans:
        if plan.action not in {"CREATE", "UPDATE"}:
            continue
        values = plan.values
        if plan.action == "CREATE":
            group = Group.objects.create(name=values["name"])
            profile = ensure_group_profile(group)
            profile.codename = values["codename"]
        else:
            profile = GroupProfile.objects.select_related("group").get(pk=plan.expected["pk"])
            group = profile.group
            group.name = values["name"]
            group.save(update_fields=["name"])
        profile.description = values["description"]
        profile.full_clean()
        profile.save()
        sync_group_permission_assignments(group, values["bundles"])


def render_role_plans(plans):
    lines = ["[auth.Group] 默认业务角色（不分配成员或技术领域）", ""]
    for plan in plans:
        values = plan.values
        lines.append(f"{plan.action} {values['codename']}（{values['name']}）")
        lines.append(f"    说明：{values['description']}")
        for key in ("name", "description", "bundles"):
            old = plan.expected[key] if plan.expected else "空"
            lines.append(f"    {key}: {old} -> {values[key]}")
        lines.append(
            f"    保留现有成员、领域和额外原生权限；现有成员数：{len(plan.expected['members']) if plan.expected else 0}"
        )
        lines.append(f"    展开权限：{', '.join(plan.permission_labels)}")
        lines.append("")
    return lines
