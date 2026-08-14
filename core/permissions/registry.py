from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from django.apps import apps
from django.contrib.auth.models import Permission

from core.config_loader import ConfigurationError, load_yaml_mapping


CATALOG_PATH = Path(__file__).resolve().parent.parent / "config" / "permission_bundles.yml"
CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
PERMISSION_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


class PermissionBundleCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class PermissionBundleSpec:
    code: str
    name: str
    description: str
    permissions: tuple[str, ...]

    @property
    def permission_labels(self) -> tuple[str, ...]:
        return self.permissions


def _require_exact_keys(value: dict, expected: set[str], location: str) -> None:
    actual = set(value)
    if actual != expected:
        raise PermissionBundleCatalogError(
            f"{location} 字段必须恰好为 {sorted(expected)}，实际为 {sorted(actual)}。"
        )


@lru_cache(maxsize=1)
def get_permission_bundle_specs() -> tuple[PermissionBundleSpec, ...]:
    try:
        raw = load_yaml_mapping(CATALOG_PATH)
    except ConfigurationError as exc:
        raise PermissionBundleCatalogError(str(exc)) from exc
    _require_exact_keys(raw, {"version", "bundles"}, "权限包目录顶层")
    if raw["version"] != 1:
        raise PermissionBundleCatalogError("权限包目录只支持 version: 1。")
    if not isinstance(raw["bundles"], list):
        raise PermissionBundleCatalogError("bundles 必须是列表。")

    specs = []
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    for index, item in enumerate(raw["bundles"], start=1):
        location = f"bundles[{index}]"
        if not isinstance(item, dict):
            raise PermissionBundleCatalogError(f"{location} 必须是 mapping。")
        _require_exact_keys(item, {"code", "name", "description", "permissions"}, location)
        code, name, description, labels = (
            item["code"], item["name"], item["description"], item["permissions"]
        )
        if not isinstance(code, str) or not CODE_PATTERN.fullmatch(code):
            raise PermissionBundleCatalogError(f"{location}.code 格式无效：{code!r}。")
        if not isinstance(name, str) or not name.strip():
            raise PermissionBundleCatalogError(f"{location}.name 必须是非空字符串。")
        if not isinstance(description, str) or not description.strip():
            raise PermissionBundleCatalogError(f"{location}.description 必须是非空字符串。")
        if code in seen_codes:
            raise PermissionBundleCatalogError(f"权限包 code 重复：{code}。")
        if name in seen_names:
            raise PermissionBundleCatalogError(f"权限包 name 重复：{name}。")
        if not isinstance(labels, list) or not labels:
            raise PermissionBundleCatalogError(f"{location}.permissions 必须是非空列表。")
        if any(not isinstance(label, str) or not PERMISSION_PATTERN.fullmatch(label) for label in labels):
            raise PermissionBundleCatalogError(f"{location}.permissions 包含格式无效的权限。")
        if len(labels) != len(set(labels)):
            raise PermissionBundleCatalogError(f"{location}.permissions 包含重复权限。")
        specs.append(PermissionBundleSpec(code, name.strip(), description.strip(), tuple(labels)))
        seen_codes.add(code)
        seen_names.add(name)
    return tuple(specs)


def get_permission_bundle_choices() -> list[tuple[str, str]]:
    return [(spec.code, spec.name) for spec in get_permission_bundle_specs()]


def get_permission_bundle_spec_map() -> dict[str, PermissionBundleSpec]:
    return {spec.code: spec for spec in get_permission_bundle_specs()}


def normalize_permission_bundle_codes(bundle_codes: Iterable[str] | None) -> list[str]:
    known = get_permission_bundle_spec_map()
    normalized: list[str] = []
    for code in bundle_codes or ():
        if code not in known:
            raise PermissionBundleCatalogError(f"未知权限包 code：{code!r}。")
        if code not in normalized:
            normalized.append(code)
    return normalized


def get_declared_permission_labels() -> dict[str, list[str]]:
    labels: dict[str, list[str]] = {}
    for model in apps.get_models():
        opts = model._meta
        for action in opts.default_permissions:
            label = f"{opts.app_label}.{action}_{opts.model_name}"
            labels.setdefault(label, []).append(opts.label_lower)
        for codename, _name in opts.permissions:
            labels.setdefault(f"{opts.app_label}.{codename}", []).append(opts.label_lower)
    return labels


def validate_declared_permissions() -> None:
    declared = get_declared_permission_labels()
    for spec in get_permission_bundle_specs():
        for label in spec.permissions:
            matches = declared.get(label, [])
            if not matches:
                raise PermissionBundleCatalogError(f"权限包 {spec.code} 引用了不存在的权限 {label}。")
            if len(matches) > 1:
                raise PermissionBundleCatalogError(
                    f"权限包 {spec.code} 引用了不唯一的权限 {label}：{matches}。"
                )


def get_permissions_for_bundle_codes(bundle_codes: Iterable[str] | None):
    codes = normalize_permission_bundle_codes(bundle_codes)
    specs = get_permission_bundle_spec_map()
    labels = {label for code in codes for label in specs[code].permissions}
    if not labels:
        return Permission.objects.none()
    app_labels = {label.split(".", 1)[0] for label in labels}
    codenames = {label.split(".", 1)[1] for label in labels}
    found: dict[str, list[Permission]] = {}
    queryset = Permission.objects.filter(
        content_type__app_label__in=app_labels,
        codename__in=codenames,
    ).select_related("content_type")
    for permission in queryset:
        label = f"{permission.content_type.app_label}.{permission.codename}"
        if label in labels:
            found.setdefault(label, []).append(permission)
    for label in sorted(labels):
        matches = found.get(label, [])
        if not matches:
            raise PermissionBundleCatalogError(f"数据库中缺少权限 {label}。请先执行迁移。")
        if len(matches) > 1:
            raise PermissionBundleCatalogError(f"数据库中的权限 {label} 不唯一。")
    ids = [matches[0].pk for matches in found.values()]
    return Permission.objects.filter(pk__in=ids).select_related("content_type")


def get_users_with_explicit_permission(permission_name, queryset=None):
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    queryset = queryset if queryset is not None else get_user_model().objects.all()
    app_label, codename = permission_name.split(".", 1)
    return queryset.filter(
        Q(user_permissions__content_type__app_label=app_label, user_permissions__codename=codename)
        | Q(groups__permissions__content_type__app_label=app_label, groups__permissions__codename=codename)
    ).distinct()
