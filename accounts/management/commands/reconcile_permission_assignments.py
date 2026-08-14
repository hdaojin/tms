from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import GroupProfile, UserProfile
from accounts.services.permission_assignments import (
    sync_group_permission_assignments,
    sync_user_permission_assignments,
)
from core.permissions import PermissionBundleCatalogError, get_permissions_for_bundle_codes


class Command(BaseCommand):
    help = "检查权限包与显式权限生成的原生权限投影；默认只报告，--apply 才修复。"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="应用检测到的投影修复。")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        group_drift = []
        user_drift = []
        try:
            for group in Group.objects.order_by("pk"):
                profile = GroupProfile.objects.filter(group=group).first()
                codes = profile.selected_permission_bundles if profile else []
                explicit_ids = set(
                    profile.explicit_permissions.values_list("pk", flat=True)
                ) if profile else set()
                desired = set(
                    get_permissions_for_bundle_codes(codes).values_list("pk", flat=True)
                ) | explicit_ids
                current = set(group.permissions.values_list("pk", flat=True))
                if current != desired:
                    group_drift.append((group, profile, codes, desired))

            for user in get_user_model().objects.order_by("pk"):
                profile = UserProfile.objects.filter(user=user).first()
                codes = profile.selected_permission_bundles if profile else []
                explicit_ids = set(
                    profile.explicit_permissions.values_list("pk", flat=True)
                ) if profile else set()
                desired = set(
                    get_permissions_for_bundle_codes(codes).values_list("pk", flat=True)
                ) | explicit_ids
                current = set(user.user_permissions.values_list("pk", flat=True))
                if current != desired:
                    user_drift.append((user, profile, codes, desired))
        except PermissionBundleCatalogError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"检测完成：用户组漂移 {len(group_drift)} 个，用户漂移 {len(user_drift)} 个。"
        )
        if not apply_changes:
            self.stdout.write("当前为 dry-run；使用 --apply 应用修复。")
            return

        with transaction.atomic():
            for group, profile, codes, desired in group_drift:
                if profile:
                    sync_group_permission_assignments(
                        group, codes, profile.explicit_permissions.all()
                    )
                else:
                    group.permissions.set(desired)
            for user, profile, codes, desired in user_drift:
                if profile:
                    sync_user_permission_assignments(
                        user, codes, profile.explicit_permissions.all()
                    )
                else:
                    user.user_permissions.set(desired)
        self.stdout.write(self.style.SUCCESS("权限投影已完成修复。"))
