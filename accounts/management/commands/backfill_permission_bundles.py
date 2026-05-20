from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

from accounts.models import GroupProfile, UserProfile
from accounts.services.permission_bundles import (
    infer_permission_bundle_codes_from_permissions,
    sync_group_permission_bundles,
    sync_user_permission_bundles,
)
from core.permissions import normalize_permission_bundle_codes


@dataclass
class BackfillPlan:
    kind: str
    label: str
    obj: object
    bundle_codes: list[str]
    extra_permissions: list[Permission]


class Command(BaseCommand):
    help = "根据现有用户/用户组的直授权限回填业务权限包选择。默认仅预检查，追加 --execute 才会写库。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="实际写入业务权限包；默认仅输出预检查结果。",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="即使当前已存在业务权限包选择，也按现有直授权限重新推断。",
        )
        parser.add_argument(
            "--groups-only",
            action="store_true",
            help="只回填用户组。",
        )
        parser.add_argument(
            "--users-only",
            action="store_true",
            help="只回填用户。",
        )

    def handle(self, *args, **options):
        groups_only = options["groups_only"]
        users_only = options["users_only"]
        execute = options["execute"]
        overwrite = options["overwrite"]

        if groups_only and users_only:
            raise CommandError("--groups-only 与 --users-only 不能同时使用。")

        plans: list[BackfillPlan] = []
        if not users_only:
            plans.extend(self._collect_group_plans(overwrite))
        if not groups_only:
            plans.extend(self._collect_user_plans(overwrite))

        if not plans:
            self.stdout.write(self.style.SUCCESS("当前没有可回填的业务权限包。"))
            return

        for plan in plans:
            bundles_text = ", ".join(plan.bundle_codes)
            extras_text = ", ".join(self._format_permission_labels(plan.extra_permissions)) or "无"
            self.stdout.write(
                f"- {plan.kind} {plan.label}: 业务权限包 -> {bundles_text}; 额外原生权限 -> {extras_text}"
            )

        if not execute:
            self.stdout.write(self.style.WARNING("以上为预检查结果。确认无误后，请追加 --execute 写入数据库。"))
            return

        for plan in plans:
            if plan.kind == "用户组":
                sync_group_permission_bundles(plan.obj, plan.bundle_codes, plan.extra_permissions)
            else:
                sync_user_permission_bundles(plan.obj, plan.bundle_codes, plan.extra_permissions)

        self.stdout.write(self.style.SUCCESS(f"已回填 {len(plans)} 个对象的业务权限包。"))

    def _collect_group_plans(self, overwrite: bool) -> list[BackfillPlan]:
        plans: list[BackfillPlan] = []
        for group in Group.objects.order_by("id"):
            existing_codes = self._get_group_existing_bundle_codes(group)
            if existing_codes and not overwrite:
                continue
            bundle_codes, extra_permissions = infer_permission_bundle_codes_from_permissions(
                group.permissions.all()
            )
            if not bundle_codes:
                continue
            plans.append(
                BackfillPlan(
                    kind="用户组",
                    label=group.name,
                    obj=group,
                    bundle_codes=bundle_codes,
                    extra_permissions=list(extra_permissions),
                )
            )
        return plans

    def _collect_user_plans(self, overwrite: bool) -> list[BackfillPlan]:
        plans: list[BackfillPlan] = []
        user_model = get_user_model()
        for user in user_model.objects.order_by("id"):
            existing_codes = self._get_user_existing_bundle_codes(user)
            if existing_codes and not overwrite:
                continue
            bundle_codes, extra_permissions = infer_permission_bundle_codes_from_permissions(
                user.user_permissions.all()
            )
            if not bundle_codes:
                continue
            plans.append(
                BackfillPlan(
                    kind="用户",
                    label=user.username,
                    obj=user,
                    bundle_codes=bundle_codes,
                    extra_permissions=list(extra_permissions),
                )
            )
        return plans

    def _get_group_existing_bundle_codes(self, group: Group) -> list[str]:
        profile = GroupProfile.objects.filter(group=group).only("selected_permission_bundles").first()
        if profile is None:
            return []
        return normalize_permission_bundle_codes(profile.selected_permission_bundles)

    def _get_user_existing_bundle_codes(self, user) -> list[str]:
        profile = UserProfile.objects.filter(user=user).only("selected_permission_bundles").first()
        if profile is None:
            return []
        return normalize_permission_bundle_codes(profile.selected_permission_bundles)

    def _format_permission_labels(self, permissions: list[Permission]) -> list[str]:
        return [f"{permission.content_type.app_label}.{permission.codename}" for permission in permissions]