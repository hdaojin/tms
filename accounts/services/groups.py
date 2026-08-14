from __future__ import annotations

import re

from django.contrib.auth.models import Group

from accounts.models import GroupProfile


def build_unique_group_codename(preferred: str, group: Group) -> str:
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
        trimmed = candidate[: 29 - len(str(suffix))]
        fallback = f"{trimmed}_{suffix}"
        if fallback not in existing:
            return fallback
        suffix += 1


def ensure_group_profile(group: Group) -> GroupProfile:
    profile, _created = GroupProfile.objects.get_or_create(
        group=group,
        defaults={
            "codename": build_unique_group_codename(group.name, group),
            "description": f"{group.name}用户组",
        },
    )
    if not profile.codename:
        profile.codename = build_unique_group_codename(group.name, group)
        profile.full_clean()
        profile.save(update_fields=["codename"])
    return profile
