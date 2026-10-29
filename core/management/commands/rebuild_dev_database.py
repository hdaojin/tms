"""显式重建开发数据库；不重放历史数据迁移，也不清理上传文件。"""

from importlib import import_module

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from accounts.bootstrap import DEFAULT_ROLES
from core.bootstrap_engine import BOOTSTRAP_MODULES, bootstrap_defaults


class Command(BaseCommand):
    help = "仅限 DEBUG=True：清空开发数据库的数据，并按当前 Bootstrap 声明重建默认数据；保留上传文件。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只预览清理范围和当前默认数据，不写数据库。")
        parser.add_argument("--yes", action="store_true", help="显示预览后自动确认清空开发数据库。")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("开发数据库重建仅允许在 DEBUG=True 时执行；数据库未写入。")
        if connection.vendor not in {"sqlite", "postgresql"}:
            raise CommandError("开发数据库重建仅支持 SQLite 和 PostgreSQL；数据库未写入。")
        if settings.DATABASE_ROUTERS or len(settings.DATABASES) != 1:
            raise CommandError("开发数据库重建仅支持无数据库路由的单数据库配置；数据库未写入。")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError("存在未应用的迁移，请先执行 uv run manage.py migrate；数据库未写入。")

        config = connection.settings_dict
        self.stdout.write("开发数据库重建预览")
        self.stdout.write(f"目标：{DEFAULT_DB_ALIAS} / {config['ENGINE']} / {config['NAME']}")
        if connection.vendor == "postgresql":
            self.stdout.write(f"主机：{config.get('HOST') or '本机'}，端口：{config.get('PORT') or '默认'}")
        self.stdout.write("将清空全部应用表中的业务数据、全部账号（含超级管理员）、会话和配置。")
        self.stdout.write("保留数据库结构和迁移记录；上传文件保留，附件记录清空。")
        self.stdout.write("请先停止开发服务和其他数据库写入进程。")
        tables = sorted(connection.introspection.django_table_names(only_existing=True, include_views=False))
        all_tables = set(connection.introspection.table_names())
        extra_tables = all_tables - set(tables) - {"django_migrations"}
        if extra_tables:
            raise CommandError("发现当前应用之外的表，无法保证完整重建：" + "、".join(sorted(extra_tables)))
        with connection.cursor() as cursor:
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {connection.ops.quote_name(table)}")
                self.stdout.write(f"  {table}：{cursor.fetchone()[0]} 行")
        self.stdout.write("重建内容：Django 内容类型、权限和站点，以及当前 Bootstrap 默认数据：")
        for module_name in BOOTSTRAP_MODULES:
            for dataset in import_module(module_name).BOOTSTRAP_DATA:
                records = dataset.get("records")
                if records is None:
                    records = dataset["records_factory"](force=False, database_is_empty=True)
                names = [
                    str(next(
                        (row[key] for key in ("name", "title", "display_name", "site_name", "code", "parser_key") if key in row),
                        "/".join(str(row.get(key, "")) for key in dataset["key_fields"]),
                    ))
                    for row in records
                ]
                self.stdout.write(f"  {dataset['label']}（{len(records)} 项）：{'、'.join(names)}")
        self.stdout.write("  默认账号角色：" + "、".join(role["name"] for role in DEFAULT_ROLES))
        self.stdout.write("不会创建账号，不会重放历史数据迁移中的旧默认数据。")
        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("预览完成；数据库未写入。"))
            return
        if not options["yes"]:
            try:
                answer = input("确认清空以上开发数据库并重建？请输入 yes：")
            except EOFError as exc:
                raise CommandError("无法读取确认输入；使用 --dry-run 预览或 --yes 显式确认。") from exc
            if answer.strip().lower() != "yes":
                self.stdout.write("已取消；数据库未写入。")
                return

        try:
            with transaction.atomic():
                # flush 使用 SQL 清空表，不触发模型删除信号，因而不会删除上传文件。
                # post_migrate 恢复权限和站点，但不会重放 RunPython 数据迁移。
                call_command("flush", interactive=False, verbosity=0, stdout=self.stdout)
                counts = bootstrap_defaults()
        except Exception as exc:
            raise CommandError("开发数据库重建失败，数据库修改已回滚。请检查默认数据声明和数据库约束。") from exc
        finally:
            ContentType.objects.clear_cache()
            Site.objects.clear_cache()
        self.stdout.write(self.style.SUCCESS(
            f"开发数据库重建完成：CREATE={counts['CREATE']}，UPDATE={counts['UPDATE']}。上传文件已保留。"
        ))
        self.stdout.write("请执行 uv run manage.py createsuperuser 创建新的管理员账号。")
