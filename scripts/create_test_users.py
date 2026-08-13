from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.chdir(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tmsproject.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils import timezone

from accounts.models import GroupProfile, UserProfile
from accounts.services.permission_bundles import sync_group_permission_bundles
from core.constants import GROUP_COACH, GROUP_COMPETITOR
from core.permissions.roles import ROLE_COMPETITOR


PermissionSpec = tuple[str, str, str]


@dataclass(frozen=True)
class BuiltinGroupSpec:
    name: str
    codename: str
    description: str
    permission_bundles: tuple[str, ...] = ()
    extra_permissions: tuple[PermissionSpec, ...] = ()


BUILTIN_GROUP_SPECS = (
    BuiltinGroupSpec(
        name=GROUP_COACH,
        codename="coach",
        description="教练组",
        permission_bundles=(
            "traininglogs.upload_traininglog",
            "traininglogs.view_competitor_traininglogs",
        ),
    ),
    BuiltinGroupSpec(
        name=GROUP_COMPETITOR,
        codename="competitor",
        description="选手组",
        permission_bundles=(
            "traininglogs.upload_traininglog",
            "traininglogs.view_coach_traininglogs",
        ),
    ),
    BuiltinGroupSpec(
        name="班务",
        codename="assistant",
        description="班务组",
        permission_bundles=(
            "meetings.upload_meeting",
            "notices.publish_notice",
        ),
    ),
)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("数量必须为正整数")
    return parsed


def sanitize_username_part(value: str) -> str:
    sanitized = re.sub(r"[^\w.@+-]+", "_", value).strip("_")
    return sanitized or "test"


def build_unique_codename(preferred: str, group: Group) -> str:
    existing = set(
        GroupProfile.objects.exclude(group=group).values_list("codename", flat=True)
    )
    candidate = re.sub(r"[^a-zA-Z0-9_]+", "_", preferred).strip("_") or f"group_{group.pk}"
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


def find_group_spec(group_name: str) -> BuiltinGroupSpec | None:
    for spec in BUILTIN_GROUP_SPECS:
        if spec.name == group_name:
            return spec
    return None


def ensure_group_profile(group: Group, spec: BuiltinGroupSpec | None = None) -> GroupProfile:
    preferred_codename = spec.codename if spec is not None else f"group_{group.pk}"
    description = spec.description if spec is not None else f"{group.name}用户组"

    profile, _ = GroupProfile.objects.get_or_create(
        group=group,
        defaults={
            "codename": build_unique_codename(preferred_codename, group),
            "description": description,
        },
    )

    updated_fields: list[str] = []
    if not profile.codename:
        profile.codename = build_unique_codename(preferred_codename, group)
        updated_fields.append("codename")
    if not profile.description:
        profile.description = description
        updated_fields.append("description")

    if updated_fields:
        profile.full_clean()
        profile.save(update_fields=updated_fields)

    return profile


def resolve_permissions(permissions: tuple[PermissionSpec, ...]) -> list[Permission]:
    resolved_permissions: list[Permission] = []
    for codename, app_label, model_name in permissions:
        permission = Permission.objects.filter(
            codename=codename,
            content_type__app_label=app_label,
            content_type__model=model_name,
        ).first()
        if permission is not None:
            resolved_permissions.append(permission)
    return resolved_permissions


def ensure_builtin_groups() -> list[Group]:
    groups: list[Group] = []
    for spec in BUILTIN_GROUP_SPECS:
        group, _ = Group.objects.get_or_create(name=spec.name)
        ensure_group_profile(group, spec)
        sync_group_permission_bundles(
            group,
            spec.permission_bundles,
            resolve_permissions(spec.extra_permissions),
        )
        groups.append(group)
    return groups


def collect_target_groups(include_existing_groups: bool) -> list[Group]:
    groups_by_id = {group.pk: group for group in ensure_builtin_groups()}

    if include_existing_groups:
        for group in Group.objects.order_by("id"):
            if group.pk not in groups_by_id:
                ensure_group_profile(group, find_group_spec(group.name))
                groups_by_id[group.pk] = group

    return sorted(groups_by_id.values(), key=lambda group: group.id)


def next_sequence(username_prefix: str) -> int:
    user_model = get_user_model()
    pattern = re.compile(rf"^{re.escape(username_prefix)}_(\d+)$")
    max_sequence = 0
    for username in user_model.objects.filter(
        username__startswith=f"{username_prefix}_"
    ).values_list("username", flat=True):
        match = pattern.fullmatch(username)
        if match is not None:
            max_sequence = max(max_sequence, int(match.group(1)))
    return max_sequence + 1


def build_student_id(user, group_profile: GroupProfile) -> str | None:
    if group_profile.codename != ROLE_COMPETITOR:
        return None
    return f"S{group_profile.group_id:02d}{user.pk:08d}"


def create_profile(user, group: Group, group_profile: GroupProfile, sequence: int) -> None:
    is_competitor = group_profile.codename == ROLE_COMPETITOR
    profile = UserProfile(
        user=user,
        student_id=build_student_id(user, group_profile),
        name_pronunciation=user.username,
        gender=UserProfile.Gender.MALE if sequence % 2 else UserProfile.Gender.FEMALE,
        join_date=timezone.localdate() if is_competitor else None,
        original_class=f"{group.name}测试班" if is_competitor else None,
        notes=f"由 create_test_users.py 创建的{group.name}测试用户",
    )
    profile.full_clean()
    profile.save()


def create_users_for_group(group: Group, count: int, prefix: str, password: str) -> list[str]:
    user_model = get_user_model()
    group_profile = ensure_group_profile(group, find_group_spec(group.name))
    username_prefix = f"{sanitize_username_part(prefix)}_{sanitize_username_part(group_profile.codename)}"
    starting_sequence = next_sequence(username_prefix)
    created_usernames: list[str] = []

    for offset in range(count):
        sequence = starting_sequence + offset
        username = f"{username_prefix}_{sequence:03d}"
        with transaction.atomic():
            user = user_model.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password=password,
                first_name=f"测试{sequence:03d}",
                last_name=group.name,
                is_active=True,
            )
            user.groups.add(group)
            create_profile(user, group, group_profile, sequence)
        created_usernames.append(username)

    return created_usernames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建测试用户，并覆盖每个内置组")
    parser.add_argument(
        "count",
        nargs="?",
        type=positive_int,
        default=3,
        help="每个组要创建的测试用户数量，默认 3",
    )
    parser.add_argument(
        "--password",
        default="testpass123",
        help="测试用户统一密码，默认 testpass123",
    )
    parser.add_argument(
        "--prefix",
        default="test",
        help="用户名公共前缀，默认 test",
    )
    parser.add_argument(
        "--include-existing-groups",
        action="store_true",
        help="除内置组外，也为数据库中现有其他组创建测试用户",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    groups = collect_target_groups(args.include_existing_groups)

    if not groups:
        print("未找到任何可用用户组。")
        return

    total_created = 0
    for group in groups:
        usernames = create_users_for_group(group, args.count, args.prefix, args.password)
        total_created += len(usernames)
        print(f"{group.name}: 新建 {len(usernames)} 个用户 -> {', '.join(usernames)}")

    print(f"成功创建 {total_created} 个测试用户，统一密码为: {args.password}")


if __name__ == "__main__":
    main()
