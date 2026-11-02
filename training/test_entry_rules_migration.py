from datetime import date, datetime, timezone

from django.core.exceptions import FieldDoesNotExist
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class EntryRulesMigrationTests(TransactionTestCase):
    def test_flags_equal_coaches_and_withdrawal_preserve_records(self):
        before = ("training", "0016_unconfigured_slot_constraint")
        after = ("training", "0017_staged_schedule_and_equal_coaches")
        executor = MigrationExecutor(connection)
        executor.migrate([before])
        try:
            apps = executor.loader.project_state([before]).apps
            user = apps.get_model("auth", "User").objects.create(username="migration-coach")
            project = apps.get_model("standards", "SkillProject").objects.create(code="ENTRY", name="迁移项目")
            domain = apps.get_model("standards", "TechnicalDomain").objects.create(
                skill_project=project, code="L", name="Linux"
            )
            cycle = apps.get_model("training", "TrainingCycle").objects.create(
                skill_project=project, code="ENTRY", name="迁移周期", start_date=date(2026, 1, 1)
            )
            published = datetime(2026, 1, 1, tzinfo=timezone.utc)
            plan = apps.get_model("training", "TrainingPlan").objects.create(
                training_cycle=cycle,
                title="旧计划",
                objective="保留",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 3),
                created_by=user,
                published_at=published,
                schedule_published_at=published,
            )
            Day, Slot = (
                apps.get_model("training", "TrainingScheduleDay"),
                apps.get_model("training", "TrainingScheduleSlot"),
            )
            day = Day.objects.create(training_plan=plan, date=date(2026, 1, 1))
            day.duty_coaches.add(user)
            untouched = Day.objects.create(training_plan=plan, date=date(2026, 1, 2), revision=99)
            cleared = Day.objects.create(training_plan=plan, date=date(2026, 1, 3))
            slot = Slot.objects.create(
                day=day, period="morning", kind="technical", primary_domain=domain, primary_coach=user
            )
            slot.domains.add(domain)
            slot.coaches.add(user)
            task = apps.get_model("training", "TrainingTask").objects.create(
                training_plan=plan, schedule_slot=slot, planned_date=day.date, title="历史任务", created_by=user
            )
            relation = apps.get_model("training", "TrainingTaskCoach").objects.create(
                training_task=task, user=user, role="primary"
            )
            record = apps.get_model("training", "TrainingChangeRecord").objects.create(
                training_plan=plan,
                actor=user,
                action="保存排班",
                after={
                    "调整": [{"type": "day", "id": cleared.pk, "before": {"note": "曾填写"}, "after": {"note": ""}}]
                },
            )
            original = record.after
            executor = MigrationExecutor(connection)
            executor.migrate([after])
            apps = executor.loader.project_state([after]).apps
            Day, Slot = (
                apps.get_model("training", "TrainingScheduleDay"),
                apps.get_model("training", "TrainingScheduleSlot"),
            )
            self.assertTrue(Day.objects.get(pk=day.pk).has_been_filled)
            self.assertFalse(Day.objects.get(pk=untouched.pk).has_been_filled)
            self.assertTrue(Day.objects.get(pk=cleared.pk).has_been_filled)
            self.assertTrue(Slot.objects.get(pk=slot.pk).has_been_filled)
            self.assertEqual(list(Slot.objects.get(pk=slot.pk).coaches.values_list("pk", flat=True)), [user.pk])
            Coach = apps.get_model("training", "TrainingTaskCoach")
            self.assertEqual(Coach.objects.get(pk=relation.pk).user_id, user.pk)
            with self.assertRaises(FieldDoesNotExist):
                Coach._meta.get_field("role")
            with self.assertRaises(FieldDoesNotExist):
                Slot._meta.get_field("primary_coach")
            migrated = apps.get_model("training", "TrainingPlan").objects.get(pk=plan.pk)
            self.assertIsNone(migrated.schedule_published_at)
            self.assertEqual(migrated.published_at, published)
            self.assertTrue(apps.get_model("training", "TrainingTask").objects.filter(pk=task.pk).exists())
            self.assertEqual(
                apps.get_model("training", "TrainingChangeRecord").objects.get(pk=record.pk).after, original
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
