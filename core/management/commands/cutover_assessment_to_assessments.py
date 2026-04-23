import shutil
from dataclasses import dataclass

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from assessments.models import Assessment, AssessmentAttachment, AssessmentModule, Score
from core.constants import ASSESSMENT_UPLOAD_DIR


OLD_APP_LABEL = "assessment"
NEW_APP_LABEL = "assessments"


@dataclass(frozen=True)
class TableRename:
    label: str
    old_name: str
    new_name: str
    model: object


@dataclass(frozen=True)
class TableAction:
    plan: TableRename
    mode: str


class Command(BaseCommand):
    help = "把旧 assessment app 的数据库元数据与私有文件目录切换到 assessments。默认仅预检查，追加 --execute 才会实际修改。"

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
        table_actions = self._collect_table_actions(connection, table_plan, existing_tables)
        migration_action = self._collect_metadata_action(connection, "django_migrations", "app")
        content_type_action = self._collect_content_type_action(database)
        media_action = self._collect_media_action()

        has_actions = any((table_actions, migration_action, content_type_action, media_action))
        if not has_actions:
            self.stdout.write(self.style.SUCCESS("当前数据库与文件目录已经使用 assessments，无需切换。"))
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
        self.stdout.write(self.style.SUCCESS("assessment 已切换为 assessments。接下来请运行 manage.py migrate。"))

    def _get_table_plan(self):
        return [
            TableRename("Assessment", "assessment_assessment", Assessment._meta.db_table, Assessment),
            TableRename(
                "AssessmentModule",
                "assessment_assessmentmodule",
                AssessmentModule._meta.db_table,
                AssessmentModule,
            ),
            TableRename(
                "AssessmentAttachment",
                "assessment_assessmentattachment",
                AssessmentAttachment._meta.db_table,
                AssessmentAttachment,
            ),
            TableRename("Score", "assessment_score", Score._meta.db_table, Score),
            TableRename(
                "Assessment.participants",
                "assessment_assessment_participants",
                Assessment.participants.through._meta.db_table,
                Assessment.participants.through,
            ),
        ]

    def _collect_table_actions(self, connection, table_plan, existing_tables):
        actions = []
        for plan in table_plan:
            old_exists = plan.old_name in existing_tables
            new_exists = plan.new_name in existing_tables
            if old_exists and new_exists:
                if self._table_has_rows(connection, plan.new_name):
                    raise CommandError(
                        f"检测到旧表和新表同时存在，且新表 {plan.new_name} 已有数据。当前状态不完整，请先人工确认。"
                    )
                actions.append(TableAction(plan=plan, mode="recover-dual-table"))
                continue
            if old_exists:
                actions.append(TableAction(plan=plan, mode="rename-old-table"))
        return actions

    def _table_has_rows(self, connection, table_name):
        quoted_name = connection.ops.quote_name(table_name)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT 1 FROM {quoted_name} LIMIT 1")
            return cursor.fetchone() is not None

    def _collect_metadata_action(self, connection, table_name, column_name):
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT name FROM {table_name} WHERE {column_name} = %s",
                [OLD_APP_LABEL],
            )
            old_names = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                f"SELECT name FROM {table_name} WHERE {column_name} = %s",
                [NEW_APP_LABEL],
            )
            new_names = {row[0] for row in cursor.fetchall()}

        duplicate_names = sorted(old_names & new_names)
        rename_names = sorted(old_names - new_names)
        if duplicate_names or rename_names:
            return {
                "table": table_name,
                "column": column_name,
                "duplicate_names": duplicate_names,
                "rename_names": rename_names,
            }
        return None

    def _collect_content_type_action(self, database):
        old_models = set(
            ContentType.objects.using(database)
            .filter(app_label=OLD_APP_LABEL)
            .values_list("model", flat=True)
        )
        new_models = set(
            ContentType.objects.using(database)
            .filter(app_label=NEW_APP_LABEL)
            .values_list("model", flat=True)
        )
        if old_models:
            return {
                "duplicate_models": sorted(old_models & new_models),
                "rename_models": sorted(old_models - new_models),
            }
        return None

    def _collect_media_action(self):
        legacy_dir = ASSESSMENT_UPLOAD_DIR.parent / OLD_APP_LABEL
        new_dir = ASSESSMENT_UPLOAD_DIR
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
            if action.mode == "recover-dual-table":
                self.stdout.write(
                    f"- 恢复半切换数据表: {action.plan.old_name} -> {action.plan.new_name}（当前新表为空）"
                )
            else:
                self.stdout.write(f"- 重命名数据表: {action.plan.old_name} -> {action.plan.new_name}")
        if migration_action:
            duplicate_count = len(migration_action["duplicate_names"])
            rename_count = len(migration_action["rename_names"])
            self.stdout.write(
                f"- 收敛 django_migrations: 删除重复 {duplicate_count} 条，迁移旧记录 {rename_count} 条"
            )
        if content_type_action:
            duplicate_count = len(content_type_action["duplicate_models"])
            rename_count = len(content_type_action["rename_models"])
            self.stdout.write(
                f"- 收敛 django_content_type: 合并重复模型 {duplicate_count} 个，迁移旧模型 {rename_count} 个"
            )
        if media_action:
            self.stdout.write(
                f"- 移动私有文件目录: {media_action['old_dir']} -> {media_action['new_dir']}"
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
                        self._apply_table_actions(connection, schema_editor, table_actions)
                    self._update_metadata(database, connection, migration_action, content_type_action)
                connection.check_constraints()
            else:
                with transaction.atomic(using=database):
                    with connection.schema_editor() as schema_editor:
                        self._apply_table_actions(connection, schema_editor, table_actions)
                    self._update_metadata(database, connection, migration_action, content_type_action)
        except Exception as exc:
            if moved_media and new_dir and legacy_dir and new_dir.exists() and not legacy_dir.exists():
                shutil.move(str(new_dir), str(legacy_dir))
            raise CommandError(f"执行切换失败：{exc}") from exc

    def _apply_table_actions(self, connection, schema_editor, table_actions):
        backup_actions = []

        for action in table_actions:
            if action.mode == "rename-old-table":
                schema_editor.alter_db_table(
                    action.plan.model,
                    action.plan.old_name,
                    action.plan.new_name,
                )
                continue

            if connection.vendor == "sqlite":
                schema_editor.delete_model(action.plan.model)
                schema_editor.alter_db_table(
                    action.plan.model,
                    action.plan.old_name,
                    action.plan.new_name,
                )
                continue

            backup_name = self._build_backup_table_name(connection, action.plan.new_name)
            schema_editor.alter_db_table(
                action.plan.model,
                action.plan.new_name,
                backup_name,
            )
            backup_actions.append((action, backup_name))

        for action, backup_name in backup_actions:
            schema_editor.alter_db_table(
                action.plan.model,
                action.plan.old_name,
                action.plan.new_name,
            )

        for action, backup_name in reversed(backup_actions):
            schema_editor.execute(f"DROP TABLE {connection.ops.quote_name(backup_name)}")

    def _build_backup_table_name(self, connection, table_name):
        existing_tables = set(connection.introspection.table_names())
        candidate = f"{table_name}_empty_backup"
        suffix = 2
        while candidate in existing_tables:
            candidate = f"{table_name}_empty_backup_{suffix}"
            suffix += 1
        return candidate

    def _update_metadata(self, database, connection, migration_action, content_type_action):
        if migration_action:
            with connection.cursor() as cursor:
                for name in migration_action["duplicate_names"]:
                    cursor.execute(
                        "DELETE FROM django_migrations WHERE app = %s AND name = %s",
                        [OLD_APP_LABEL, name],
                    )
                for name in migration_action["rename_names"]:
                    cursor.execute(
                        "UPDATE django_migrations SET app = %s WHERE app = %s AND name = %s",
                        [NEW_APP_LABEL, OLD_APP_LABEL, name],
                    )

        if content_type_action:
            old_content_types = list(
                ContentType.objects.using(database).filter(app_label=OLD_APP_LABEL).order_by("id")
            )
            new_content_types = {
                content_type.model: content_type
                for content_type in ContentType.objects.using(database).filter(app_label=NEW_APP_LABEL)
            }
            for old_content_type in old_content_types:
                new_content_type = new_content_types.get(old_content_type.model)
                if new_content_type is None:
                    old_content_type.app_label = NEW_APP_LABEL
                    old_content_type.save(using=database, update_fields=["app_label"])
                    new_content_types[old_content_type.model] = old_content_type
                    continue

                self._merge_permissions(database, old_content_type, new_content_type)
                LogEntry.objects.using(database).filter(content_type_id=old_content_type.pk).update(
                    content_type_id=new_content_type.pk
                )
                old_content_type.delete(using=database)

    def _merge_permissions(self, database, old_content_type, new_content_type):
        old_permissions = Permission.objects.using(database).filter(content_type=old_content_type)
        for permission in old_permissions:
            duplicate = Permission.objects.using(database).filter(
                content_type=new_content_type,
                codename=permission.codename,
            ).exists()
            if duplicate:
                permission.delete(using=database)
                continue

            permission.content_type = new_content_type
            permission.save(using=database, update_fields=["content_type"])