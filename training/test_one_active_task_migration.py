from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class OneActiveTaskMigrationTests(TransactionTestCase):
    def test_preserves_execution_history_when_cancelling_duplicates(self):
        before = ("training", "0029_training_plan_implementation_audience")
        after = ("training", "0030_one_active_task_per_slot")
        executor = MigrationExecutor(connection)
        executor.migrate([before])
        try:
            apps = executor.loader.project_state([before]).apps
            user = apps.get_model("auth", "User").objects.create(username="task-migration")
            project = apps.get_model("standards", "SkillProject").objects.create(code="SLOT", name="时段项目")
            day_date = date(2026, 1, 1)
            cycle = apps.get_model("training", "TrainingCycle").objects.create(
                skill_project=project, code="SLOT", name="时段周期", start_date=day_date,
            )
            plan = apps.get_model("training", "TrainingPlan").objects.create(
                training_cycle=cycle, title="时段计划", start_date=day_date, end_date=day_date, created_by=user,
            )
            day = apps.get_model("training", "TrainingScheduleDay").objects.create(training_plan=plan, date=day_date)
            slot = apps.get_model("training", "TrainingScheduleSlot").objects.create(day=day, period="morning")
            tasks = apps.get_model("training", "TrainingTask").objects
            published = tasks.create(
                training_plan=plan, schedule_slot=slot, planned_date=day_date,
                created_by=user, title="已发布", status="published",
            )
            with_history = tasks.create(
                training_plan=plan, schedule_slot=slot, planned_date=day_date, created_by=user, title="有执行事实",
            )
            executions = apps.get_model("training", "TaskExecution").objects
            execution = executions.create(training_task=with_history, user=user, status="in_progress")
            old_assignment = executions.create(training_task=published, user=user)

            executor = MigrationExecutor(connection)
            executor.migrate([after])
            apps = executor.loader.project_state([after]).apps
            tasks = apps.get_model("training", "TrainingTask").objects
            self.assertEqual(tasks.get(schedule_slot_id=slot.pk, status="draft").pk, with_history.pk)
            self.assertEqual(tasks.get(pk=published.pk).status, "cancelled")
            self.assertEqual(
                set(apps.get_model("training", "TaskExecution").objects.values_list("pk", flat=True)),
                {execution.pk, old_assignment.pk},
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
