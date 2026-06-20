from __future__ import annotations

import re
from typing import Iterable

from django.contrib.auth.models import Group, Permission

from accounts.models import GroupProfile, UserProfile
from core.permissions import (
    get_permission_bundle_specs,
    get_permissions_for_bundle_codes,
    normalize_permission_bundle_codes,
)


def _build_unique_group_codename(preferred: str, group: Group) -> str:
    existing = set(
        GroupProfile.objects.exclude(group=group).values_list("codename", flat=True)
    )
    candidate = re.sub(r"[^a-zA-Z0-9_]+", "_", preferred).strip("_").lower()
    if not candidate:
        candidate = f"group_{group.pk}"
    if not candidate[0].isalpha():
        candidate = f"g_{candidate}"
    candidate = candidate[:30]

    if candidate not in existing:
        return candidate

    suffix = 2
    while True:
        trimmed = candidate[: 30 - len(str(suffix)) - 1]
        fallback = f"{trimmed}_{suffix}"
        if fallback not in existing:
            return fallback
        suffix += 1


def ensure_group_profile(group: Group) -> GroupProfile:
    profile, _created = GroupProfile.objects.get_or_create(
        group=group,
        defaults={
            "codename": _build_unique_group_codename(group.name, group),
            "description": f"{group.name}用户组",
        },
    )
    updated_fields: list[str] = []
    if not profile.codename:
        profile.codename = _build_unique_group_codename(group.name, group)
        updated_fields.append("codename")
    if updated_fields:
        profile.full_clean()
        profile.save(update_fields=updated_fields)
    return profile


def ensure_user_profile(user) -> UserProfile:
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


def get_group_permission_bundle_codes(group: Group) -> list[str]:
    if not getattr(group, "pk", None):
        return []
    profile = ensure_group_profile(group)
    return normalize_permission_bundle_codes(profile.selected_permission_bundles)


def get_user_permission_bundle_codes(user) -> list[str]:
    if not getattr(user, "pk", None):
        return []
    profile = ensure_user_profile(user)
    return normalize_permission_bundle_codes(profile.selected_permission_bundles)


def _permission_ids(permissions: Iterable[Permission] | None) -> set[int]:
    return {permission.pk for permission in permissions or [] if getattr(permission, "pk", None)}


def get_permission_bundle_permission_map() -> dict[str, set[int]]:
    permission_map: dict[str, set[int]] = {}
    for spec in get_permission_bundle_specs():
        permission_map[spec.code] = set(
            get_permissions_for_bundle_codes([spec.code]).values_list("id", flat=True)
        )
    return permission_map


def infer_permission_bundle_codes_from_permissions(
    permissions: Iterable[Permission] | None,
    permission_map: dict[str, set[int]] | None = None,
):
    direct_permission_ids = _permission_ids(permissions)
    if not direct_permission_ids:
        return [], Permission.objects.none()

    permission_map = permission_map or get_permission_bundle_permission_map()
    covered_permission_ids: set[int] = set()
    selected_bundle_codes: list[str] = []
    for spec in sorted(
        get_permission_bundle_specs(),
        key=lambda item: (-len(item.permissions), item.code),
    ):
        bundle_permission_ids = permission_map.get(spec.code, set())
        if not bundle_permission_ids:
            continue
        if not bundle_permission_ids.issubset(direct_permission_ids):
            continue
        if bundle_permission_ids.issubset(covered_permission_ids):
            continue
        selected_bundle_codes.append(spec.code)
        covered_permission_ids |= bundle_permission_ids

    extra_permission_ids = direct_permission_ids - covered_permission_ids
    extra_permissions = Permission.objects.filter(id__in=extra_permission_ids).select_related(
        "content_type"
    )
    return selected_bundle_codes, extra_permissions


def get_group_extra_permissions(group: Group):
    if not getattr(group, "pk", None):
        return Permission.objects.none()
    derived_ids = set(
        get_permissions_for_bundle_codes(get_group_permission_bundle_codes(group)).values_list("id", flat=True)
    )
    queryset = group.permissions.all().select_related("content_type")
    if not derived_ids:
        return queryset
    return queryset.exclude(id__in=derived_ids)


def get_user_extra_permissions(user):
    if not getattr(user, "pk", None):
        return Permission.objects.none()
    derived_ids = set(
        get_permissions_for_bundle_codes(get_user_permission_bundle_codes(user)).values_list("id", flat=True)
    )
    queryset = user.user_permissions.all().select_related("content_type")
    if not derived_ids:
        return queryset
    return queryset.exclude(id__in=derived_ids)


def sync_group_permission_bundles(
    group: Group,
    bundle_codes: Iterable[str] | None,
    extra_permissions: Iterable[Permission] | None = None,
):
    profile = ensure_group_profile(group)
    normalized_codes = normalize_permission_bundle_codes(bundle_codes)
    if profile.selected_permission_bundles != normalized_codes:
        profile.selected_permission_bundles = normalized_codes
        profile.save(update_fields=["selected_permission_bundles"])

    derived_ids = set(
        get_permissions_for_bundle_codes(normalized_codes).values_list("id", flat=True)
    )
    final_ids = derived_ids | _permission_ids(extra_permissions)
    group.permissions.set(final_ids)
    return group.permissions.all().select_related("content_type")


def sync_user_permission_bundles(
    user,
    bundle_codes: Iterable[str] | None,
    extra_permissions: Iterable[Permission] | None = None,
):
    profile = ensure_user_profile(user)
    normalized_codes = normalize_permission_bundle_codes(bundle_codes)
    if profile.selected_permission_bundles != normalized_codes:
        profile.selected_permission_bundles = normalized_codes
        profile.save(update_fields=["selected_permission_bundles"])

    derived_ids = set(
        get_permissions_for_bundle_codes(normalized_codes).values_list("id", flat=True)
    )
    final_ids = derived_ids | _permission_ids(extra_permissions)
    user.user_permissions.set(final_ids)
    return user.user_permissions.all().select_related("content_type")