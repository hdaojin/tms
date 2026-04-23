import shutil
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from core.constants import MEETINGS_UPLOAD_DIR
from meetings.models import Meeting


OLD_APP_LABEL = "meeting"
NEW_APP_LABEL = "meetings"


@dataclass(frozen=True)
class TableRename:
    label: str
    old_name: str
    new_name: str
    model: object


class Command(BaseCommand):
    help = "把旧 meeting app 的数据库元数据切换到 meetings。默认仅预检查，追加 --execute 才会实际修改。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="要操作的数据库别名，默认 default。",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="实际执行切换；默认仅输出预检查结果。",
        )

    def handle(self, *args, **options):
        database = options["database"]
        execute = options["execute"]
        connection = connections[database]

        table_plan = self._get_table_plan()
        existing_tables = set(connection.introspection.table_names())
        table_actions = self._collect_table_actions(table_plan, existing_tables)
        migration_action = self._collect_metadata_action(connection, "django_migrations", "app")
        content_type_action = self._collect_content_type_action(database)
        media_action = self._collect_media_action()

        has_actions = any((table_actions, migration_action, content_type_action, media_action))
        if not has_actions:
            self.stdout.write(self.style.SUCCESS("当前数据库与文件目录已经使用 meetings，无需切换。"))
            return

        self._print_plan(database, table_actions, migration_action, content_type_action, media_action)
        if not execute:
            self.stdout.write(
                self.style.WARNING("以上为预检查结果。确认无误后，请追加 --execute 执行实际切换。")
            )
            return

        self._execute_cutover(
            database=database,
            connection=connection,
            table_actions=table_actions,
            migration_action=migration_action,
            content_type_action=content_type_action,
            media_action=media_action,
        )
        self.stdout.write(self.style.SUCCESS("meeting 已切换为 meetings。接下来请运行 manage.py migrate。"))

    def _get_table_plan(self):
        return [
            TableRename("Meeting", "meeting_meeting", Meeting._meta.db_table, Meeting),
        ]

    def _collect_table_actions(self, table_plan, existing_tables):
        actions = []
        for plan in table_plan:
            old_exists = plan.old_name in existing_tables
            new_exists = plan.new_name in existing_tables
            if old_exists and new_exists:
                raise CommandError(
                    f"检测到旧表和新表同时存在：{plan.old_name} / {plan.new_name}。当前状态不完整，请先人工确认。"
                )
            if old_exists:
                actions.append(plan)
        return actions

    def _collect_metadata_action(self, connection, table_name, column_name):
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = %s",
                [OLD_APP_LABEL],
            )
            old_count = cursor.fetchone()[0]
            cursor.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = %s",
                [NEW_APP_LABEL],
            )
            new_count = cursor.fetchone()[0]

        if old_count and new_count:
            raise CommandError(
                f"检测到 {table_name}.{column_name} 同时存在 {OLD_APP_LABEL} 和 {NEW_APP_LABEL}，当前状态不完整，请先人工确认。"
            )
        if old_count:
            return {"table": table_name, "column": column_name, "count": old_count}
        return None

    def _collect_content_type_action(self, database):
        old_count = ContentType.objects.using(database).filter(app_label=OLD_APP_LABEL).count()
        new_count = ContentType.objects.using(database).filter(app_label=NEW_APP_LABEL).count()
        if old_count and new_count:
            raise CommandError(
                f"检测到 django_content_type 同时存在 {OLD_APP_LABEL} 和 {NEW_APP_LABEL}。当前状态不完整，请先人工确认。"
            )
        if old_count:
            return {"count": old_count}
        return None

    def _collect_media_action(self):
        legacy_dir = Path(settings.MEDIA_ROOT) / OLD_APP_LABEL
        new_dir = Path(settings.MEDIA_ROOT) / MEETINGS_UPLOAD_DIR
        legacy_exists = legacy_dir.exists()
        new_exists = new_dir.exists()

        if legacy_exists and new_exists and self._directory_has_files(new_dir):
            raise CommandError(
                f"检测到 {legacy_dir} 和 {new_dir} 同时存在且新目录非空。当前状态不完整，请先人工确认。"
            )
        if legacy_exists:
            return {
                "old_dir": legacy_dir,
                "new_dir": new_dir,
                "remove_placeholder": new_exists,
            }
        return None

    def _directory_has_files(self, path):
        if not path.exists():
            return False
        return any(node.is_file() for node in path.rglob("*"))

    def _print_plan(self, database, table_actions, migration_action, content_type_action, media_action):
        self.stdout.write(f"数据库: {database}")
        for action in table_actions:
            self.stdout.write(f"- 重命名数据表: {action.old_name} -> {action.new_name}")
        if migration_action:
            self.stdout.write(
                f"- 更新 django_migrations: {migration_action['count']} 条 {OLD_APP_LABEL} -> {NEW_APP_LABEL}"
            )
        if content_type_action:
            self.stdout.write(
                f"- 更新 django_content_type: {content_type_action['count']} 条 {OLD_APP_LABEL} -> {NEW_APP_LABEL}"
            )
        if media_action:
            self.stdout.write(
                f"- 移动公共文件目录: {media_action['old_dir']} -> {media_action['new_dir']}"
            )

    def _execute_cutover(
        self,
        *,
        database,
        connection,
        table_actions,
        migration_action,
        content_type_action,
        media_action,
    ):
        moved_media = False
        legacy_dir = None
        new_dir = None

        if media_action:
            legacy_dir = media_action["old_dir"]
            new_dir = media_action["new_dir"]
            if media_action["remove_placeholder"] and new_dir.exists():
                shutil.rmtree(new_dir)
            shutil.move(str(legacy_dir), str(new_dir))
            moved_media = True

        try:
            if connection.vendor == "sqlite":
                with connection.constraint_checks_disabled():
                    with connection.schema_editor(atomic=False) as schema_editor:
                        for action in table_actions:
                            schema_editor.alter_db_table(action.model, action.old_name, action.new_name)
                    self._update_metadata(database, connection, migration_action, content_type_action)
                connection.check_constraints()
            else:
                with transaction.atomic(using=database):
                    with connection.schema_editor() as schema_editor:
                        for action in table_actions:
                            schema_editor.alter_db_table(action.model, action.old_name, action.new_name)
                    self._update_metadata(database, connection, migration_action, content_type_action)
        except Exception as exc:
            if moved_media and new_dir and legacy_dir and new_dir.exists() and not legacy_dir.exists():
                shutil.move(str(new_dir), str(legacy_dir))
            raise CommandError(f"执行切换失败：{exc}") from exc

    def _update_metadata(self, database, connection, migration_action, content_type_action):
        if migration_action:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE django_migrations SET app = %s WHERE app = %s",
                    [NEW_APP_LABEL, OLD_APP_LABEL],
                )

        if content_type_action:
            ContentType.objects.using(database).filter(app_label=OLD_APP_LABEL).update(
                app_label=NEW_APP_LABEL
            )