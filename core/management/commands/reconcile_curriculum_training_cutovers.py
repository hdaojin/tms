from collections import defaultdict
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


@dataclass(frozen=True)
class TableAction:
    plan: TableRename
    mode: str


MOVED_COMPETITIONS_MODELS = [
    "competitiontype",
    "project",
    "moduleaxis",
    "standardmoduleset",
    "standardmodule",
    "standardmoduleaxismap",
]

REQUIRED_MIGRATIONS = [
    ("curriculum", "0001_initial"),
    ("trainingcycles", "0001_initial"),
    ("assessments", "0002_initial"),
]


class Command(BaseCommand):
    help = "统一预检查或执行 curriculum/trainingcycles 切换收尾，使旧数据库与当前迁移状态一致。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="要操作的数据库别名，默认 default。",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="实际执行收尾；默认仅输出预检查结果。",
        )

    def handle(self, *args, **options):
        database = options["database"]
        execute = options["execute"]
        connection = connections[database]

        existing_tables = set(connection.introspection.table_names())
        table_actions = self._collect_table_actions(connection, existing_tables)
        training_plan = self._collect_training_plan(connection, existing_tables, table_actions)
        migration_plan = self._collect_migration_plan(connection)
        content_type_plan = self._collect_content_type_plan(database)

        has_actions = any(
            (
                table_actions,
                training_plan["add_project_competition_type_column"],
                training_plan["backfill_project_competition_types"],
                training_plan["project_competition_type_unresolved"],
                training_plan["project_competition_type_ambiguous"],
                training_plan["create_trainingcycles_table"],
                training_plan["add_traininglog_cycle_column"],
                training_plan["add_assessment_cycle_column"],
                training_plan["rebuild_traininglog_unique"],
                migration_plan,
                content_type_plan,
            )
        )
        if not has_actions:
            self.stdout.write(self.style.SUCCESS("当前数据库已经与 curriculum/trainingcycles 的迁移状态一致，无需收尾。"))
            return

        self._print_plan(database, table_actions, training_plan, migration_plan, content_type_plan)
        if not execute:
            self.stdout.write(self.style.WARNING("以上为预检查结果。确认无误后，请追加 --execute 执行实际收尾。"))
            return

        unresolved_projects = training_plan["project_competition_type_unresolved"]
        if unresolved_projects:
            raise CommandError(
                "检测到无法自动推断所属赛事类型的 Project，请先人工补齐后再执行："
                f"{self._format_project_entries(unresolved_projects)}"
            )
        ambiguous_projects = training_plan["project_competition_type_ambiguous"]
        if ambiguous_projects:
            raise CommandError(
                "检测到所属赛事类型不唯一的 Project，请先人工拆分或补齐后再执行："
                f"{self._format_project_entries(ambiguous_projects)}"
            )

        self._execute_cutover(
            database=database,
            connection=connection,
            table_actions=table_actions,
            training_plan=training_plan,
            migration_plan=migration_plan,
            content_type_plan=content_type_plan,
        )
        self.stdout.write(self.style.SUCCESS("curriculum/trainingcycles 收尾已完成。接下来请重新运行 manage.py makemigrations。"))

    def _get_table_plan(self):
        return [
            TableRename("CompetitionType", "competitions_competitiontype", CompetitionType._meta.db_table, CompetitionType),
            TableRename("Project", "competitions_project", Project._meta.db_table, Project),
            TableRename("ModuleAxis", "competitions_moduleaxis", ModuleAxis._meta.db_table, ModuleAxis),
            TableRename(
                "StandardModuleSet",
                "competitions_standardmoduleset",
                StandardModuleSet._meta.db_table,
                StandardModuleSet,
            ),
            TableRename("StandardModule", "competitions_standardmodule", StandardModule._meta.db_table, StandardModule),
            TableRename(
                "StandardModuleAxisMap",
                "competitions_standardmoduleaxismap",
                StandardModuleAxisMap._meta.db_table,
                StandardModuleAxisMap,
            ),
        ]

    def _collect_table_actions(self, connection, existing_tables):
        actions = []
        for plan in self._get_table_plan():
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

    def _collect_training_plan(self, connection, existing_tables, table_actions):
        traininglogs_table = "traininglogs_traininglog"
        assessments_table = "assessments_assessment"
        project_table = None
        if "curriculum_project" in existing_tables:
            project_table = "curriculum_project"
        elif "competitions_project" in existing_tables:
            project_table = "competitions_project"
        traininglog_columns = self._get_table_columns(connection, traininglogs_table) if traininglogs_table in existing_tables else set()
        assessment_columns = self._get_table_columns(connection, assessments_table) if assessments_table in existing_tables else set()
        project_columns = self._get_table_columns(connection, project_table) if project_table else set()
        project_data_table = self._get_project_data_table(project_table, table_actions)
        project_data_columns = self._get_table_columns(connection, project_data_table) if project_data_table else set()
        project_competition_type_status = self._collect_project_competition_type_status(
            connection,
            project_data_table,
            has_competition_type_column="competition_type_id" in project_data_columns,
        )
        return {
            "add_project_competition_type_column": project_table is not None and "competition_type_id" not in project_columns,
            "backfill_project_competition_types": bool(project_competition_type_status["backfillable"]),
            "project_competition_type_backfillable": project_competition_type_status["backfillable"],
            "project_competition_type_unresolved": project_competition_type_status["unresolved"],
            "project_competition_type_ambiguous": project_competition_type_status["ambiguous"],
            "create_trainingcycles_table": TrainingCycle._meta.db_table not in existing_tables,
            "add_traininglog_cycle_column": traininglogs_table in existing_tables and "training_cycle_id" not in traininglog_columns,
            "add_assessment_cycle_column": assessments_table in existing_tables and "training_cycle_id" not in assessment_columns,
            "rebuild_traininglog_unique": traininglogs_table in existing_tables
            and (
                self._has_unique_constraint(connection, traininglogs_table, ["uploaded_by_id", "training_date"])
                or not self._has_unique_constraint(
                    connection,
                    traininglogs_table,
                    ["training_cycle_id", "uploaded_by_id", "training_date"],
                )
            ),
        }

    def _collect_migration_plan(self, connection):
        recorder = MigrationRecorder(connection)
        applied = set(recorder.applied_migrations())
        return [migration for migration in REQUIRED_MIGRATIONS if migration not in applied]

    def _collect_content_type_plan(self, database):
        old_models = set(
            ContentType.objects.using(database)
            .filter(app_label="competitions", model__in=MOVED_COMPETITIONS_MODELS)
            .values_list("model", flat=True)
        )
        new_models = set(
            ContentType.objects.using(database)
            .filter(app_label="curriculum", model__in=MOVED_COMPETITIONS_MODELS)
            .values_list("model", flat=True)
        )
        has_training_cycle = ContentType.objects.using(database).filter(
            app_label="curriculum",
            model="trainingcycle",
        ).exists()
        if old_models or not has_training_cycle:
            return {
                "duplicate_models": sorted(old_models & new_models),
                "rename_models": sorted(old_models - new_models),
                "ensure_trainingcycle": not has_training_cycle,
            }
        return None

    def _print_plan(self, database, table_actions, training_plan, migration_plan, content_type_plan):
        self.stdout.write(f"数据库: {database}")
        for action in table_actions:
            if action.mode == "recover-dual-table":
                self.stdout.write(
                    f"- 恢复半切换数据表: {action.plan.old_name} -> {action.plan.new_name}（当前新表为空）"
                )
            else:
                self.stdout.write(f"- 重命名数据表: {action.plan.old_name} -> {action.plan.new_name}")
        if training_plan["add_project_competition_type_column"]:
            self.stdout.write("- 为 curriculum_project 补充 competition_type_id，并按现有赛项关系回填所属赛事类型")
        if training_plan["backfill_project_competition_types"]:
            self.stdout.write(
                f"- 可根据现有赛项关系自动补齐 Project 的所属赛事类型："
                f"{len(training_plan['project_competition_type_backfillable'])} 个"
            )
        if training_plan["project_competition_type_unresolved"]:
            self.stdout.write("- 以下 Project 无法自动推断所属赛事类型，执行前需人工补齐：")
            for entry in training_plan["project_competition_type_unresolved"]:
                self.stdout.write(f"  - {self._format_project_entry(entry)}")
        if training_plan["project_competition_type_ambiguous"]:
            self.stdout.write("- 以下 Project 关联了多个赛事类型，执行前需人工拆分或补齐：")
            for entry in training_plan["project_competition_type_ambiguous"]:
                self.stdout.write(f"  - {self._format_project_entry(entry)}")
        if training_plan["create_trainingcycles_table"]:
            self.stdout.write(f"- 创建数据表: {TrainingCycle._meta.db_table}")
        if training_plan["add_traininglog_cycle_column"]:
            self.stdout.write("- 为 traininglogs_traininglog 补充 training_cycle_id 并按现有日志回填默认备赛周期")
        if training_plan["add_assessment_cycle_column"]:
            self.stdout.write("- 为 assessments_assessment 补充 training_cycle_id 并按现有考核模块回填默认备赛周期")
        if training_plan["rebuild_traininglog_unique"]:
            self.stdout.write("- 调整 traininglogs 旧唯一约束为“同一备赛周期 + 上传者 + 训练日期”")
        if migration_plan:
            migrations_text = ", ".join(f"{app}.{name}" for app, name in migration_plan)
            self.stdout.write(f"- 补记 django_migrations: {migrations_text}")
        if content_type_plan:
            duplicate_count = len(content_type_plan["duplicate_models"])
            rename_count = len(content_type_plan["rename_models"])
            extra = "，并补建 curriculum.trainingcycle 内容类型" if content_type_plan["ensure_trainingcycle"] else ""
            self.stdout.write(
                f"- 收敛 django_content_type: 合并重复模型 {duplicate_count} 个，迁移旧模型 {rename_count} 个{extra}"
            )

    def _execute_cutover(
        self,
        *,
        database,
        connection,
        table_actions,
        training_plan,
        migration_plan,
        content_type_plan,
    ):
        if connection.vendor == "sqlite":
            with connection.constraint_checks_disabled():
                with connection.schema_editor(atomic=False) as schema_editor:
                    self._apply_table_actions(connection, schema_editor, table_actions)
                    self._apply_training_schema_changes(connection, schema_editor, training_plan)
                self._backfill_training_cycles(database, connection)
                self._rebuild_traininglog_constraints(connection, training_plan)
                self._record_migrations(connection, migration_plan)
                self._update_content_types(database, content_type_plan)
            connection.check_constraints()
            return

        with transaction.atomic(using=database):
            with connection.schema_editor() as schema_editor:
                self._apply_table_actions(connection, schema_editor, table_actions)
                self._apply_training_schema_changes(connection, schema_editor, training_plan)
            self._backfill_training_cycles(database, connection)
            self._rebuild_traininglog_constraints(connection, training_plan)
            self._record_migrations(connection, migration_plan)
            self._update_content_types(database, content_type_plan)

    def _apply_table_actions(self, connection, schema_editor, table_actions):
        backup_actions = []

        for action in table_actions:
            if action.mode == "rename-old-table":
                schema_editor.alter_db_table(action.plan.model, action.plan.old_name, action.plan.new_name)
                continue

            if connection.vendor == "sqlite":
                schema_editor.delete_model(action.plan.model)
                schema_editor.alter_db_table(action.plan.model, action.plan.old_name, action.plan.new_name)
                continue

            backup_name = self._build_backup_table_name(connection, action.plan.new_name)
            schema_editor.alter_db_table(action.plan.model, action.plan.new_name, backup_name)
            backup_actions.append((action, backup_name))

        for action, backup_name in backup_actions:
            schema_editor.alter_db_table(action.plan.model, action.plan.old_name, action.plan.new_name)

        for action, backup_name in reversed(backup_actions):
            schema_editor.execute(f"DROP TABLE {connection.ops.quote_name(backup_name)}")

    def _apply_training_schema_changes(self, connection, schema_editor, training_plan):
        if training_plan["add_project_competition_type_column"]:
            self._add_nullable_bigint_column(connection, schema_editor, "curriculum_project", "competition_type_id")
        if training_plan["create_trainingcycles_table"]:
            schema_editor.create_model(TrainingCycle)
        if training_plan["add_traininglog_cycle_column"]:
            self._add_nullable_bigint_column(connection, schema_editor, "traininglogs_traininglog", "training_cycle_id")
        if training_plan["add_assessment_cycle_column"]:
            self._add_nullable_bigint_column(connection, schema_editor, "assessments_assessment", "training_cycle_id")

    def _backfill_training_cycles(self, database, connection):
        self._backfill_project_competition_types(connection)
        cycle_specs = self._collect_cycle_specs(connection)
        if not cycle_specs:
            return

        cycle_map = self._ensure_training_cycles(database, cycle_specs)
        self._backfill_traininglogs(connection, cycle_map)
        self._backfill_assessments(connection, cycle_map)

    def _collect_cycle_specs(self, connection):
        null_module_count = self._fetch_scalar(
            connection,
            "SELECT COUNT(*) FROM traininglogs_traininglog WHERE module_id IS NULL",
        )
        if null_module_count:
            raise CommandError("存在未关联模块的训练日志，无法自动推断备赛周期，请先人工补齐模块。")

        ambiguous_assessments = self._fetch_rows(
            connection,
            """
            SELECT pairs.id, pairs.name
            FROM (
                SELECT a.id, a.name, sm.project_id, sm.module_set_id
                FROM assessments_assessment a
                JOIN assessments_assessmentmodule am ON am.assessment_id = a.id
                JOIN curriculum_standardmodule sm ON sm.id = am.module_id
                GROUP BY a.id, a.name, sm.project_id, sm.module_set_id
            ) pairs
            GROUP BY pairs.id, pairs.name
            HAVING COUNT(*) > 1
            """,
        )
        if ambiguous_assessments:
            names = ", ".join(name for _, name in ambiguous_assessments)
            raise CommandError(f"存在跨多个项目或模块集的考核，无法自动推断备赛周期：{names}")

        assessments_without_modules = self._fetch_rows(
            connection,
            """
            SELECT a.id, a.name
            FROM assessments_assessment a
            LEFT JOIN assessments_assessmentmodule am ON am.assessment_id = a.id
            GROUP BY a.id, a.name
            HAVING COUNT(am.id) = 0
            """,
        )
        if assessments_without_modules:
            names = ", ".join(name for _, name in assessments_without_modules)
            raise CommandError(f"存在未关联任何模块的考核，无法自动推断备赛周期：{names}")

        cycle_specs = defaultdict(lambda: {"start_date": None, "end_date": None})
        for project_id, module_set_id, start_date, end_date in self._fetch_rows(
            connection,
            """
            SELECT sm.project_id, sm.module_set_id, MIN(tl.training_date), MAX(tl.training_date)
            FROM traininglogs_traininglog tl
            JOIN curriculum_standardmodule sm ON sm.id = tl.module_id
            GROUP BY sm.project_id, sm.module_set_id
            """,
        ):
            self._merge_cycle_spec(cycle_specs[(project_id, module_set_id)], start_date, end_date)

        for project_id, module_set_id, start_date, end_date in self._fetch_rows(
            connection,
            """
            SELECT sm.project_id, sm.module_set_id, MIN(a.start_date), MAX(COALESCE(a.end_date, a.start_date))
            FROM assessments_assessment a
            JOIN assessments_assessmentmodule am ON am.assessment_id = a.id
            JOIN curriculum_standardmodule sm ON sm.id = am.module_id
            GROUP BY sm.project_id, sm.module_set_id
            """,
        ):
            self._merge_cycle_spec(cycle_specs[(project_id, module_set_id)], start_date, end_date)

        return dict(cycle_specs)

    def _ensure_training_cycles(self, database, cycle_specs):
        existing_cycles = defaultdict(list)
        for cycle in TrainingCycle.objects.using(database).order_by("pk"):
            existing_cycles[(cycle.project_id, cycle.module_set_id)].append(cycle)

        cycle_map = {}
        existing_codes = set(TrainingCycle.objects.using(database).values_list("code", flat=True))
        today = timezone.localdate()

        for pair, spec in cycle_specs.items():
            current_cycles = existing_cycles.get(pair)
            if current_cycles:
                cycle_map[pair] = current_cycles[0].pk
                continue

            project = Project.objects.using(database).get(pk=pair[0])
            module_set = StandardModuleSet.objects.using(database).get(pk=pair[1])
            code = self._build_legacy_cycle_code(existing_codes, pair)
            existing_codes.add(code)
            start_date = self._normalize_date(spec["start_date"]) or today
            end_date = self._normalize_date(spec["end_date"])
            if end_date and end_date < today:
                status = TrainingCycle.Status.COMPLETED
            elif start_date > today:
                status = TrainingCycle.Status.PLANNING
            else:
                status = TrainingCycle.Status.ACTIVE

            cycle = TrainingCycle.objects.using(database).create(
                code=code,
                name=(f"{project.name} 历史导入周期")[:100],
                project=project,
                module_set=module_set,
                start_date=start_date,
                end_date=end_date,
                status=status,
                description="系统根据既有训练日志与考核数据自动生成，用于兼容训练周期切换。",
            )
            cycle_map[pair] = cycle.pk

        return cycle_map

    def _backfill_traininglogs(self, connection, cycle_map):
        columns = self._get_table_columns(connection, "traininglogs_traininglog")
        if "training_cycle_id" not in columns:
            return

        updates = []
        for row_id, project_id, module_set_id in self._fetch_rows(
            connection,
            """
            SELECT tl.id, sm.project_id, sm.module_set_id
            FROM traininglogs_traininglog tl
            JOIN curriculum_standardmodule sm ON sm.id = tl.module_id
            WHERE tl.training_cycle_id IS NULL
            """,
        ):
            cycle_id = cycle_map.get((project_id, module_set_id))
            if cycle_id is None:
                raise CommandError(
                    f"训练日志 {row_id} 无法匹配备赛周期，请先检查其模块所属项目与模块集。"
                )
            updates.append((cycle_id, row_id))

        if not updates:
            return

        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE traininglogs_traininglog SET training_cycle_id = %s WHERE id = %s",
                updates,
            )

    def _backfill_assessments(self, connection, cycle_map):
        columns = self._get_table_columns(connection, "assessments_assessment")
        if "training_cycle_id" not in columns:
            return

        updates = []
        for assessment_id, project_id, module_set_id in self._fetch_rows(
            connection,
            """
            SELECT a.id, sm.project_id, sm.module_set_id
            FROM assessments_assessment a
            JOIN assessments_assessmentmodule am ON am.assessment_id = a.id
            JOIN curriculum_standardmodule sm ON sm.id = am.module_id
            WHERE a.training_cycle_id IS NULL
            GROUP BY a.id, sm.project_id, sm.module_set_id
            """,
        ):
            cycle_id = cycle_map.get((project_id, module_set_id))
            if cycle_id is None:
                raise CommandError(
                    f"考核 {assessment_id} 无法匹配备赛周期，请先检查其模块所属项目与模块集。"
                )
            updates.append((cycle_id, assessment_id))

        if not updates:
            return

        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE assessments_assessment SET training_cycle_id = %s WHERE id = %s",
                updates,
            )

    def _backfill_project_competition_types(self, connection):
        columns = self._get_table_columns(connection, "curriculum_project")
        if "competition_type_id" not in columns:
            return

        updates = []
        for project_id, competition_type_id in self._fetch_rows(
            connection,
            """
            SELECT inferred.project_id, MIN(inferred.competition_type_id)
            FROM (
                SELECT cp.project_id, c.competition_type_id
                FROM competitions_competitionproject cp
                JOIN competitions_competition c ON c.id = cp.competition_id
                GROUP BY cp.project_id, c.competition_type_id
            ) inferred
            GROUP BY inferred.project_id
            HAVING COUNT(*) = 1
            """,
        ):
            updates.append((competition_type_id, project_id))

        if not updates:
            return

        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE curriculum_project SET competition_type_id = %s "
                "WHERE id = %s AND competition_type_id IS NULL",
                updates,
            )

    def _get_project_data_table(self, project_table, table_actions):
        for action in table_actions:
            if action.plan.label == "Project":
                return action.plan.old_name
        return project_table

    def _collect_project_competition_type_status(self, connection, project_table, *, has_competition_type_column):
        if not project_table:
            return {"backfillable": [], "unresolved": [], "ambiguous": []}

        condition = "WHERE p.competition_type_id IS NULL" if has_competition_type_column else ""
        rows = self._fetch_rows(
            connection,
            f"""
            SELECT p.id, p.code, p.name, MIN(c.competition_type_id), COUNT(DISTINCT c.competition_type_id)
            FROM {project_table} p
            LEFT JOIN competitions_competitionproject cp ON cp.project_id = p.id
            LEFT JOIN competitions_competition c ON c.id = cp.competition_id
            {condition}
            GROUP BY p.id, p.code, p.name
            ORDER BY p.id
            """,
        )

        backfillable = []
        unresolved = []
        ambiguous = []
        for project_id, code, name, inferred_competition_type_id, competition_type_count in rows:
            entry = {"id": project_id, "code": code, "name": name}
            if inferred_competition_type_id is None:
                unresolved.append(entry)
            elif competition_type_count > 1:
                ambiguous.append(entry)
            else:
                backfillable.append(entry)

        return {
            "backfillable": backfillable,
            "unresolved": unresolved,
            "ambiguous": ambiguous,
        }

    def _format_project_entry(self, entry):
        return f"ID={entry['id']}，code={entry['code']}，name={entry['name']}"

    def _format_project_entries(self, entries):
        return "；".join(self._format_project_entry(entry) for entry in entries)

    def _rebuild_traininglog_constraints(self, connection, training_plan):
        if not training_plan["rebuild_traininglog_unique"]:
            return

        old_constraints = self._get_unique_constraints(
            connection,
            "traininglogs_traininglog",
            ["uploaded_by_id", "training_date"],
        )
        with connection.cursor() as cursor:
            for name, details in old_constraints:
                self._drop_unique_definition(
                    cursor,
                    connection,
                    "traininglogs_traininglog",
                    name,
                    details,
                )

            if not self._has_unique_constraint(
                connection,
                "traininglogs_traininglog",
                ["training_cycle_id", "uploaded_by_id", "training_date"],
            ):
                self._create_unique_definition(
                    cursor,
                    connection,
                    "traininglogs_traininglog",
                    "unique_training_log_per_cycle_user_date",
                    ["training_cycle_id", "uploaded_by_id", "training_date"],
                )

    def _record_migrations(self, connection, migration_plan):
        recorder = MigrationRecorder(connection)
        for app_label, name in migration_plan:
            if (app_label, name) in recorder.applied_migrations():
                continue
            recorder.record_applied(app_label, name)

    def _update_content_types(self, database, content_type_plan):
        if not content_type_plan:
            return

        old_content_types = list(
            ContentType.objects.using(database)
            .filter(app_label="competitions", model__in=MOVED_COMPETITIONS_MODELS)
            .order_by("id")
        )
        new_content_types = {
            content_type.model: content_type
            for content_type in ContentType.objects.using(database).filter(
                app_label="curriculum",
                model__in=MOVED_COMPETITIONS_MODELS,
            )
        }
        for old_content_type in old_content_types:
            new_content_type = new_content_types.get(old_content_type.model)
            if new_content_type is None:
                old_content_type.app_label = "curriculum"
                old_content_type.save(using=database, update_fields=["app_label"])
                new_content_types[old_content_type.model] = old_content_type
                continue

            self._merge_permissions(database, old_content_type, new_content_type)
            LogEntry.objects.using(database).filter(content_type_id=old_content_type.pk).update(
                content_type_id=new_content_type.pk
            )
            old_content_type.delete(using=database)

        if content_type_plan["ensure_trainingcycle"]:
            ContentType.objects.using(database).get_or_create(
                app_label="curriculum",
                model="trainingcycle",
            )

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

    def _add_nullable_bigint_column(self, connection, schema_editor, table_name, column_name):
        schema_editor.execute(
            f"ALTER TABLE {connection.ops.quote_name(table_name)} "
            f"ADD COLUMN {connection.ops.quote_name(column_name)} bigint NULL"
        )

    def _build_backup_table_name(self, connection, table_name):
        existing_tables = set(connection.introspection.table_names())
        candidate = f"{table_name}_empty_backup"
        suffix = 2
        while candidate in existing_tables:
            candidate = f"{table_name}_empty_backup_{suffix}"
            suffix += 1
        return candidate

    def _build_legacy_cycle_code(self, existing_codes, pair):
        base = f"LEGACY-P{pair[0]}-MS{pair[1]}"
        candidate = base
        suffix = 2
        while candidate in existing_codes:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _merge_cycle_spec(self, spec, start_date, end_date):
        start_date = self._normalize_date(start_date)
        end_date = self._normalize_date(end_date)
        if start_date and (spec["start_date"] is None or start_date < spec["start_date"]):
            spec["start_date"] = start_date
        if end_date and (spec["end_date"] is None or end_date > spec["end_date"]):
            spec["end_date"] = end_date

    def _normalize_date(self, value):
        if value is None or hasattr(value, "year"):
            return value
        return timezone.datetime.fromisoformat(str(value)).date()

    def _table_has_rows(self, connection, table_name):
        quoted_name = connection.ops.quote_name(table_name)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT 1 FROM {quoted_name} LIMIT 1")
            return cursor.fetchone() is not None

    def _get_table_columns(self, connection, table_name):
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table_name)
        return {column.name for column in description}

    def _get_constraints(self, connection, table_name):
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(cursor, table_name)

    def _has_unique_constraint(self, connection, table_name, columns):
        return bool(self._get_unique_constraints(connection, table_name, columns))

    def _get_unique_constraints(self, connection, table_name, columns):
        constraints = self._get_constraints(connection, table_name)
        matches = []
        for name, details in constraints.items():
            if details.get("unique") and list(details.get("columns") or []) == list(columns):
                matches.append((name, details))
        return matches

    def _get_unique_constraint_names(self, connection, table_name, columns):
        return [name for name, _ in self._get_unique_constraints(connection, table_name, columns)]

    def _drop_unique_definition(self, cursor, connection, table_name, name, details):
        quoted_name = connection.ops.quote_name(name)
        quoted_table = connection.ops.quote_name(table_name)
        if connection.vendor == "postgresql" and not details.get("index"):
            cursor.execute(f"ALTER TABLE {quoted_table} DROP CONSTRAINT {quoted_name}")
            return
        if connection.vendor == "mysql":
            cursor.execute(f"ALTER TABLE {quoted_table} DROP INDEX {quoted_name}")
            return
        cursor.execute(f"DROP INDEX {quoted_name}")

    def _create_unique_definition(self, cursor, connection, table_name, name, columns):
        quoted_name = connection.ops.quote_name(name)
        quoted_table = connection.ops.quote_name(table_name)
        quoted_columns = ", ".join(connection.ops.quote_name(column) for column in columns)
        if connection.vendor in {"postgresql", "mysql"}:
            cursor.execute(
                f"ALTER TABLE {quoted_table} ADD CONSTRAINT {quoted_name} UNIQUE ({quoted_columns})"
            )
            return
        cursor.execute(f"CREATE UNIQUE INDEX {quoted_name} ON {quoted_table} ({quoted_columns})")

    def _fetch_scalar(self, connection, sql):
        with connection.cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()
        return row[0] if row else 0

    def _fetch_rows(self, connection, sql):
        with connection.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
