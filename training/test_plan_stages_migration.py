from datetime import date, datetime, timezone

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PlanStagesMigrationTests(TransactionTestCase):
    def test_preserves_history_and_only_extracts_consistent_plan_times(self):
        before = ("training", "0013_training_snapshot_constraint_and_status_label")
        after = ("training", "0014_plan_publication_times_and_change_confirmations")
        executor = MigrationExecutor(connection)
        executor.migrate([before])
        try:
            apps = executor.loader.project_state([before]).apps
            user = apps.get_model("auth", "User").objects.create(username="stage-migration")
            project = apps.get_model("standards", "SkillProject").objects.create(code="STAGES", name="迁移项目")
            cycle = apps.get_model("training", "TrainingCycle").objects.create(skill_project=project, code="STAGES", name="迁移周期", start_date=date(2026, 1, 1))
            published = datetime(2026, 1, 1, tzinfo=timezone.utc)
            plan = apps.get_model("training", "TrainingPlan").objects.create(training_cycle=cycle, title="历史计划", objective="保留", start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), created_by=user, schedule_published_at=published, status="published")
            Day = apps.get_model("training", "TrainingScheduleDay")
            Slot = apps.get_model("training", "TrainingScheduleSlot")
            for day in (1, 2):
                record = Day.objects.create(training_plan=plan, date=date(2026, 1, day))
                Slot.objects.create(day=record, period="morning", starts_at=datetime(2026, 1, day, day, tzinfo=timezone.utc), ends_at=datetime(2026, 1, day, 4, tzinfo=timezone.utc))
                Slot.objects.create(day=record, period="afternoon", starts_at=datetime(2026, 1, day, 6, tzinfo=timezone.utc), ends_at=datetime(2026, 1, day, 9, tzinfo=timezone.utc))
            original = list(Slot.objects.values_list("pk", "starts_at", "ends_at"))
            change = apps.get_model("training", "TrainingScheduleChange").objects.create(training_plan=plan, requested_by=user, reason="旧流程申请", payload=[])
            executor = MigrationExecutor(connection)
            executor.migrate([after])
            apps = executor.loader.project_state([after]).apps
            migrated = apps.get_model("training", "TrainingPlan").objects.get(pk=plan.pk)
            self.assertEqual(migrated.published_at, published)
            self.assertIsNone(migrated.morning_start)
            self.assertEqual(migrated.afternoon_start.hour, 14)
            self.assertEqual(migrated.afternoon_end.hour, 17)
            self.assertEqual(list(apps.get_model("training", "TrainingScheduleSlot").objects.values_list("pk", "starts_at", "ends_at")), original)
            migrated_change = apps.get_model("training", "TrainingScheduleChange").objects.get(pk=change.pk)
            self.assertEqual(migrated_change.status, "rejected")
            self.assertIn("升级", migrated_change.review_note)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
