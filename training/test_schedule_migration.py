from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ScheduleMigrationTests(TransactionTestCase):
    """用旧结构中的真实关联验证新增排班不会重建历史任务。"""

    migrate_from = ("training", "0009_log_templates_and_document_types")
    migrate_to = ("training", "0010_alter_trainingplan_options_trainingplan_approvers_and_more")

    def test_legacy_task_execution_and_log_identity_survives(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        try:
            apps = executor.loader.project_state([self.migrate_from]).apps
            user = apps.get_model("auth", "User").objects.create(username="legacy-migration-user")
            project = apps.get_model("standards", "SkillProject").objects.create(code="LEGACY", name="历史项目")
            cycle = apps.get_model("training", "TrainingCycle").objects.create(
                skill_project=project,
                code="LEGACY",
                name="历史周期",
                start_date=date(2026, 1, 1),
            )
            plan = apps.get_model("training", "TrainingPlan").objects.create(
                training_cycle=cycle,
                title="历史计划",
                objective="历史目标",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                created_by=user,
            )
            task = apps.get_model("training", "TrainingTask").objects.create(
                training_plan=plan,
                planned_date=date(2026, 1, 2),
                title="历史任务",
                requirements="保留要求",
                created_by=user,
            )
            execution = apps.get_model("training", "TaskExecution").objects.create(training_task=task, user=user)
            log = apps.get_model("training", "TrainingLog").objects.create(
                training_cycle=cycle, training_date=date(2026, 1, 2), author=user
            )
            link = apps.get_model("training", "TrainingLogExecution").objects.create(
                training_log=log, task_execution=execution
            )
            created, updated = task.created_at, task.updated_at
            executor = MigrationExecutor(connection)
            executor.migrate([self.migrate_to])
            apps = executor.loader.project_state([self.migrate_to]).apps
            migrated = apps.get_model("training", "TrainingTask").objects.get(pk=task.pk)
            self.assertIsNone(migrated.schedule_slot_id)
            self.assertEqual(migrated.training_plan_id, plan.pk)
            self.assertEqual((migrated.title, migrated.requirements), ("历史任务", "保留要求"))
            self.assertEqual((migrated.created_at, migrated.updated_at), (created, updated))
            self.assertEqual(
                apps.get_model("training", "TaskExecution").objects.get(pk=execution.pk).training_task_id, task.pk
            )
            self.assertEqual(
                apps.get_model("training", "TrainingLogExecution").objects.get(pk=link.pk).task_execution_id,
                execution.pk,
            )
            self.assertEqual(apps.get_model("training", "TrainingScheduleDay").objects.count(), 0)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
