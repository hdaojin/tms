from __future__ import annotations

from typing import Iterable

from django.contrib.auth.models import Group, Permission
from django.db import transaction

from accounts.models import GroupProfile, UserProfile
from core.permissions import (
    get_permissions_for_bundle_codes,
    normalize_permission_bundle_codes,
)

from .groups import ensure_group_profile


def _permission_ids(permissions: Iterable[Permission] | None) -> set[int]:
    return {
        permission.pk
        for permission in permissions or ()
        if getattr(permission, "pk", None) is not None
    }


def get_group_permission_bundle_codes(group: Group) -> list[str]:
    if not group.pk:
        return []
    profile = GroupProfile.objects.filter(group=group).first()
    if profile is None:
        return []
    return normalize_permission_bundle_codes(profile.selected_permission_bundles)


def get_user_permission_bundle_codes(user) -> list[str]:
    if not user.pk:
        return []
    profile = UserProfile.objects.filter(user=user).first()
    if profile is None:
        return []
    return normalize_permission_bundle_codes(profile.selected_permission_bundles)


def get_group_explicit_permissions(group: Group):
    if not group.pk:
        return Permission.objects.none()
    profile = GroupProfile.objects.filter(group=group).first()
    if profile is None:
        return Permission.objects.none()
    return profile.explicit_permissions.select_related("content_type")


def get_user_explicit_permissions(user):
    if not user.pk:
        return Permission.objects.none()
    profile = UserProfile.objects.filter(user=user).first()
    if profile is None:
        return Permission.objects.none()
    return profile.explicit_permissions.select_related("content_type")


@transaction.atomic
def sync_group_permission_assignments(
    group: Group,
    bundle_codes: Iterable[str] | None,
    explicit_permissions: Iterable[Permission] | None = None,
):
    normalized_codes = normalize_permission_bundle_codes(bundle_codes)
    profile = ensure_group_profile(group)
    profile = GroupProfile.objects.select_for_update().get(pk=profile.pk)
    explicit_ids = (
        _permission_ids(explicit_permissions)
        if explicit_permissions is not None
        else set(profile.explicit_permissions.values_list("pk", flat=True))
    )
    derived_ids = set(
        get_permissions_for_bundle_codes(normalized_codes).values_list("pk", flat=True)
    )
    profile.selected_permission_bundles = normalized_codes
    profile.save(update_fields=["selected_permission_bundles"])
    profile.explicit_permissions.set(explicit_ids)
    group.permissions.set(derived_ids | explicit_ids)
    return group.permissions.select_related("content_type")


@transaction.atomic
def sync_user_permission_assignments(
    user,
    bundle_codes: Iterable[str] | None,
    explicit_permissions: Iterable[Permission] | None = None,
):
    normalized_codes = normalize_permission_bundle_codes(bundle_codes)
    profile, _created = UserProfile.objects.get_or_create(user=user)
    profile = UserProfile.objects.select_for_update().get(pk=profile.pk)
    explicit_ids = (
        _permission_ids(explicit_permissions)
        if explicit_permissions is not None
        else set(profile.explicit_permissions.values_list("pk", flat=True))
    )
    derived_ids = set(
        get_permissions_for_bundle_codes(normalized_codes).values_list("pk", flat=True)
    )
    profile.selected_permission_bundles = normalized_codes
    profile.save(update_fields=["selected_permission_bundles"])
    profile.explicit_permissions.set(explicit_ids)
    user.user_permissions.set(derived_ids | explicit_ids)
    return user.user_permissions.select_related("content_type")
