from dataclasses import dataclass

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from competition_standards.models import (
    CompetitionType,
    ModuleAxis,
    Project,
    StandardModule,
    StandardModuleAxisMap,
    StandardModuleSet,
    TrainingCycle,
)


@dataclass(frozen=True)
class TableRename:
    label: str
    old_name: str
    new_name: str
    model: object
    old_app_label: str
    model_name: str


@dataclass(frozen=True)
class TableAction:
    plan: TableRename
    drop_empty_target_first: bool = False


TABLE_RENAMES = [
    TableRename('赛事类型', 'curriculum_competitiontype', 'competition_standards_competitiontype', CompetitionType, 'curriculum', 'competitiontype'),
    TableRename('标准赛项', 'curriculum_project', 'competition_standards_project', Project, 'curriculum', 'project'),
    TableRename('标准模块版本', 'curriculum_standardmoduleset', 'competition_standards_standardmoduleset', StandardModuleSet, 'curriculum', 'standardmoduleset'),
    TableRename('能力主线', 'curriculum_moduleaxis', 'competition_standards_moduleaxis', ModuleAxis, 'curriculum', 'moduleaxis'),
    TableRename('标准模块', 'curriculum_standardmodule', 'competition_standards_standardmodule', StandardModule, 'curriculum', 'standardmodule'),
    TableRename('标准模块能力主线映射', 'curriculum_standardmoduleaxismap', 'competition_standards_standardmoduleaxismap', StandardModuleAxisMap, 'curriculum', 'standardmoduleaxismap'),
    TableRename('训练周期', 'trainingcycles_trainingcycle', 'competition_standards_trainingcycle', TrainingCycle, 'trainingcycles', 'trainingcycle'),
]

MOVED_MODEL_NAMES = [plan.model_name for plan in TABLE_RENAMES]
LEGACY_TARGET_COLUMNS = (
    ('primary_competition_project_id', 'primary', '主目标赛项'),
    ('reference_competition_project_id', 'reference', '参考赛项'),
)
TARGET_RELATION_TABLE = 'competitions_competitiontrainingcycletarget'


class Command(BaseCommand):
    help = '将 curriculum/trainingcycles 旧表一次性切换到 competition_standards，并迁移训练周期目标赛项数据。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--database',
            default='default',
            help='要操作的数据库别名，默认 default。',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            help='实际执行切换；默认仅输出预检查结果。',
        )

    def handle(self, *args, **options):
        database = options['database']
        execute = options['execute']
        connection = connections[database]

        existing_tables = set(connection.introspection.table_names())
        table_actions = self._collect_table_actions(connection, existing_tables)
        if not table_actions and all(plan.new_name in existing_tables for plan in TABLE_RENAMES):
            self.stdout.write(self.style.SUCCESS('当前数据库已经完成 competition_standards 切换，无需操作。'))
            return
        if not table_actions:
            self.stdout.write(self.style.WARNING('未检测到可切换的旧表；如果这是全新数据库，请直接运行 migrate。'))
            return

        self._validate_complete_legacy_tables(existing_tables)
        target_columns = self._collect_legacy_target_columns(connection, existing_tables)
        relation_table_action = self._collect_relation_table_action(existing_tables, target_columns)
        content_type_count = self._count_legacy_content_types(database)
        migration_cleanup_count = self._count_legacy_migrations(connection)

        self._print_plan(
            database=database,
            table_actions=table_actions,
            target_columns=target_columns,
            relation_table_action=relation_table_action,
            content_type_count=content_type_count,
            migration_cleanup_count=migration_cleanup_count,
        )
        if not execute:
            self.stdout.write(self.style.WARNING('以上为预检查结果。确认无误后，请追加 --execute 执行实际切换。'))
            return

        self._execute_cutover(
            database=database,
            connection=connection,
            table_actions=table_actions,
            target_columns=target_columns,
            relation_table_action=relation_table_action,
        )
        self.stdout.write(self.style.SUCCESS('competition_standards 切换已完成。接下来请运行 uv run manage.py migrate。'))

    def _collect_table_actions(self, connection, existing_tables):
        actions = []
        for plan in TABLE_RENAMES:
            old_exists = plan.old_name in existing_tables
            new_exists = plan.new_name in existing_tables
            if old_exists and new_exists and self._table_has_rows(connection, plan.new_name):
                raise CommandError(
                    f'检测到旧表 {plan.old_name} 与目标表 {plan.new_name} 同时存在，且目标表已有数据。'
                    '为避免数据分叉，已中止切换。'
                )
            if old_exists:
                actions.append(TableAction(plan=plan, drop_empty_target_first=new_exists))
        return actions

    def _validate_complete_legacy_tables(self, existing_tables):
        missing = [
            plan.old_name
            for plan in TABLE_RENAMES
            if plan.old_name not in existing_tables and plan.new_name not in existing_tables
        ]
        if missing:
            raise CommandError(
                '检测到旧表不完整，无法安全切换。缺少数据表：'
                f'{", ".join(missing)}。请先确认数据库是否处于完整旧版本状态。'
            )

    def _collect_legacy_target_columns(self, connection, existing_tables):
        table_name = 'trainingcycles_trainingcycle'
        if table_name not in existing_tables:
            table_name = 'competition_standards_trainingcycle'
        if table_name not in existing_tables:
            return []
        columns = self._get_table_columns(connection, table_name)
        return [column for column, _kind, _label in LEGACY_TARGET_COLUMNS if column in columns]

    def _collect_relation_table_action(self, existing_tables, target_columns):
        if not target_columns:
            return None
        return 'create' if TARGET_RELATION_TABLE not in existing_tables else 'reuse'

    def _print_plan(
        self,
        *,
        database,
        table_actions,
        target_columns,
        relation_table_action,
        content_type_count,
        migration_cleanup_count,
    ):
        self.stdout.write(f'数据库: {database}')
        for action in table_actions:
            prefix = '删除空目标表后重命名' if action.drop_empty_target_first else '重命名'
            self.stdout.write(f'- {prefix}: {action.plan.old_name} -> {action.plan.new_name}（{action.plan.label}）')
        if target_columns:
            self.stdout.write('- 迁移训练周期旧目标赛项字段到 competitions_competitiontrainingcycletarget')
            self.stdout.write(f'- 删除训练周期旧目标赛项字段: {", ".join(target_columns)}')
            if relation_table_action == 'create':
                self.stdout.write('- 创建 competitions_competitiontrainingcycletarget 数据表并补记对应迁移')
        if content_type_count:
            self.stdout.write(f'- 更新 django_content_type / auth_permission / django_admin_log 归属：{content_type_count} 个旧内容类型')
        self.stdout.write('- 补记 competition_standards.0001_initial 已应用')
        if migration_cleanup_count:
            self.stdout.write(f'- 清理 curriculum / trainingcycles 的旧迁移记录：{migration_cleanup_count} 条')

    def _execute_cutover(self, *, database, connection, table_actions, target_columns, relation_table_action):
        if connection.vendor == 'sqlite':
            with connection.constraint_checks_disabled():
                self._execute_cutover_steps(database, connection, table_actions, target_columns, relation_table_action)
            connection.check_constraints()
            return

        with transaction.atomic(using=database):
            self._execute_cutover_steps(database, connection, table_actions, target_columns, relation_table_action)

    def _execute_cutover_steps(self, database, connection, table_actions, target_columns, relation_table_action):
        with connection.schema_editor(atomic=False) as schema_editor:
            self._apply_table_actions(connection, schema_editor, table_actions)
            if relation_table_action == 'create':
                self._create_relation_table(schema_editor)

        if target_columns:
            self._migrate_legacy_cycle_targets(connection)
            self._drop_legacy_cycle_target_columns(connection, target_columns)

        self._update_content_types(database)
        self._record_migrations(connection, relation_table_exists=bool(target_columns))
        self._delete_legacy_migration_records(connection)

    def _apply_table_actions(self, connection, schema_editor, table_actions):
        for action in table_actions:
            if action.drop_empty_target_first:
                schema_editor.delete_model(action.plan.model)
            schema_editor.alter_db_table(action.plan.model, action.plan.old_name, action.plan.new_name)

    def _create_relation_table(self, schema_editor):
        from competitions.models import CompetitionTrainingCycleTarget

        schema_editor.create_model(CompetitionTrainingCycleTarget)

    def _migrate_legacy_cycle_targets(self, connection):
        now = timezone.now()
        with connection.cursor() as cursor:
            for source_column, kind, _label in LEGACY_TARGET_COLUMNS:
                if source_column not in self._get_table_columns(connection, 'competition_standards_trainingcycle'):
                    continue
                cursor.execute(
                    f"""
                    INSERT INTO {self._quote(connection, TARGET_RELATION_TABLE)}
                        (training_cycle_id, competition_project_id, kind, created_at, updated_at)
                    SELECT tc.id, tc.{self._quote(connection, source_column)}, %s, %s, %s
                    FROM {self._quote(connection, 'competition_standards_trainingcycle')} tc
                    WHERE tc.{self._quote(connection, source_column)} IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1
                          FROM {self._quote(connection, TARGET_RELATION_TABLE)} target
                          WHERE target.training_cycle_id = tc.id
                            AND target.kind = %s
                      )
                    """,
                    [kind, now, now, kind],
                )

    def _drop_legacy_cycle_target_columns(self, connection, target_columns):
        if connection.vendor == 'sqlite':
            self._rebuild_sqlite_training_cycle_table(connection)
            return

        with connection.cursor() as cursor:
            for column_name in target_columns:
                self._drop_column_constraints(cursor, connection, 'competition_standards_trainingcycle', column_name)
                cursor.execute(
                    f'ALTER TABLE {self._quote(connection, "competition_standards_trainingcycle")} '
                    f'DROP COLUMN {self._quote(connection, column_name)}'
                )

    def _rebuild_sqlite_training_cycle_table(self, connection):
        table_name = 'competition_standards_trainingcycle'
        new_table_name = '__new_competition_standards_trainingcycle'
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA foreign_keys = OFF')
            cursor.execute(f'DROP TABLE IF EXISTS {self._quote(connection, new_table_name)}')
            cursor.execute(
                f"""
                CREATE TABLE {self._quote(connection, new_table_name)} (
                    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "code" varchar(50) NOT NULL UNIQUE,
                    "name" varchar(100) NOT NULL,
                    "start_date" date NOT NULL,
                    "end_date" date NULL,
                    "status" varchar(20) NOT NULL,
                    "description" text NOT NULL,
                    "created_at" datetime NOT NULL,
                    "updated_at" datetime NOT NULL,
                    "module_set_id" bigint NOT NULL
                        REFERENCES "competition_standards_standardmoduleset" ("id")
                        DEFERRABLE INITIALLY DEFERRED,
                    "project_id" bigint NOT NULL
                        REFERENCES "competition_standards_project" ("id")
                        DEFERRABLE INITIALLY DEFERRED
                )
                """
            )
            cursor.execute(
                f"""
                INSERT INTO {self._quote(connection, new_table_name)}
                    (id, code, name, start_date, end_date, status, description, created_at, updated_at, module_set_id, project_id)
                SELECT id, code, name, start_date, end_date, status, description, created_at, updated_at, module_set_id, project_id
                FROM {self._quote(connection, table_name)}
                """
            )
            cursor.execute(f'DROP TABLE {self._quote(connection, table_name)}')
            cursor.execute(
                f'ALTER TABLE {self._quote(connection, new_table_name)} RENAME TO {self._quote(connection, table_name)}'
            )
            cursor.execute(
                'CREATE INDEX "competition_standards_trainingcycle_module_set_id_idx" '
                'ON "competition_standards_trainingcycle" ("module_set_id")'
            )
            cursor.execute(
                'CREATE INDEX "competition_standards_trainingcycle_project_id_idx" '
                'ON "competition_standards_trainingcycle" ("project_id")'
            )
            cursor.execute('PRAGMA foreign_keys = ON')

    def _drop_column_constraints(self, cursor, connection, table_name, column_name):
        constraints = self._get_constraints(connection, table_name)
        for name, details in constraints.items():
            columns = details.get('columns') or []
            if column_name not in columns:
                continue
            quoted_table = self._quote(connection, table_name)
            quoted_name = self._quote(connection, name)
            if details.get('foreign_key') and connection.vendor == 'mysql':
                cursor.execute(f'ALTER TABLE {quoted_table} DROP FOREIGN KEY {quoted_name}')
            elif details.get('foreign_key') or (details.get('unique') and not details.get('index')):
                cursor.execute(f'ALTER TABLE {quoted_table} DROP CONSTRAINT {quoted_name}')
            elif details.get('index') or details.get('unique'):
                cursor.execute(f'DROP INDEX {quoted_name}')

    def _update_content_types(self, database):
        content_types = list(
            ContentType.objects.using(database)
            .filter(app_label__in=['curriculum', 'trainingcycles'], model__in=MOVED_MODEL_NAMES)
            .order_by('id')
        )
        targets = {
            content_type.model: content_type
            for content_type in ContentType.objects.using(database).filter(
                app_label='competition_standards',
                model__in=MOVED_MODEL_NAMES,
            )
        }

        for old_content_type in content_types:
            target = targets.get(old_content_type.model)
            if target is None:
                old_content_type.app_label = 'competition_standards'
                old_content_type.save(using=database, update_fields=['app_label'])
                targets[old_content_type.model] = old_content_type
                continue

            self._merge_permissions(database, old_content_type, target)
            LogEntry.objects.using(database).filter(content_type_id=old_content_type.pk).update(content_type_id=target.pk)
            old_content_type.delete(using=database)

        ContentType.objects.clear_cache()

    def _merge_permissions(self, database, old_content_type, new_content_type):
        old_permissions = Permission.objects.using(database).filter(content_type=old_content_type)
        for old_permission in old_permissions:
            duplicate = Permission.objects.using(database).filter(
                content_type=new_content_type,
                codename=old_permission.codename,
            ).first()
            if duplicate is None:
                old_permission.content_type = new_content_type
                old_permission.save(using=database, update_fields=['content_type'])
                continue

            for group in old_permission.group_set.using(database).all():
                group.permissions.add(duplicate)
            for user in old_permission.user_set.using(database).all():
                user.user_permissions.add(duplicate)
            old_permission.delete(using=database)

    def _record_migrations(self, connection, *, relation_table_exists):
        recorder = MigrationRecorder(connection)
        applied = set(recorder.applied_migrations())
        if ('competition_standards', '0001_initial') not in applied:
            recorder.record_applied('competition_standards', '0001_initial')
        if relation_table_exists and ('competitions', '0004_competitiontrainingcycletarget') not in applied:
            recorder.record_applied('competitions', '0004_competitiontrainingcycletarget')

    def _delete_legacy_migration_records(self, connection):
        recorder = MigrationRecorder(connection)
        recorder.Migration.objects.using(connection.alias).filter(app__in=['curriculum', 'trainingcycles']).delete()

    def _count_legacy_content_types(self, database):
        return ContentType.objects.using(database).filter(
            app_label__in=['curriculum', 'trainingcycles'],
            model__in=MOVED_MODEL_NAMES,
        ).count()

    def _count_legacy_migrations(self, connection):
        recorder = MigrationRecorder(connection)
        if not recorder.has_table():
            return 0
        return recorder.Migration.objects.using(connection.alias).filter(app__in=['curriculum', 'trainingcycles']).count()

    def _table_has_rows(self, connection, table_name):
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT 1 FROM {self._quote(connection, table_name)} LIMIT 1')
            return cursor.fetchone() is not None

    def _get_table_columns(self, connection, table_name):
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table_name)
        return {column.name for column in description}

    def _get_constraints(self, connection, table_name):
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(cursor, table_name)

    def _quote(self, connection, name):
        return connection.ops.quote_name(name)
