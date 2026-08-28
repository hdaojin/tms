from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from core.bootstrap_engine import (
    BootstrapPlanError,
    apply_bootstrap_plan,
    build_bootstrap_plan,
    render_bootstrap_plan,
)


class Command(BaseCommand):
    help = "预览并显式初始化 TMS 的默认业务目录和 Registry 运行配置。"
    requires_migrations_checks = True

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="强制恢复 Bootstrap 已声明记录的受管字段；不删除额外数据。",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只输出完整预览，不询问确认且不写数据库。",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="输出完整预览后自动确认执行。",
        )

    def handle(self, *args, **options):
        force = options["force"]
        dry_run = options["dry_run"]
        assume_yes = options["yes"]

        plan = build_bootstrap_plan(force=force)
        self.stdout.write(render_bootstrap_plan(plan))

        if plan.has_errors:
            raise CommandError("Bootstrap 预检失败；数据库未写入。")
        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry-run 完成；数据库未写入。"))
            return
        if not plan.has_changes:
            self.stdout.write(self.style.SUCCESS("无需修改；数据库未写入。"))
            return
        if not assume_yes:
            try:
                answer = input("是否执行以上修改？ [y/N]: ")
            except EOFError as exc:
                raise CommandError(
                    "无法读取确认输入；自动化场景请使用 --yes 或 --dry-run。"
                ) from exc
            if answer.strip().lower() not in {"y", "yes"}:
                self.stdout.write(self.style.WARNING("已取消；数据库未写入。"))
                return

        try:
            counts = apply_bootstrap_plan(plan)
        except (BootstrapPlanError, ValidationError, IntegrityError) as exc:
            raise CommandError(f"Bootstrap 执行失败，所有修改已回滚：{exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f'TMS 默认业务目录初始化完成：CREATE={counts["CREATE"]}，UPDATE={counts["UPDATE"]}。'
            )
        )
