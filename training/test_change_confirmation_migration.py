from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class ChangeConfirmationMigrationTests(TransactionTestCase):
    def test_only_unfinished_legacy_coach_confirmations_go_to_final_review(self):
        before = ("training", "0036_schedule_change_consultation")
        after = ("training", "0037_parallel_change_confirmation")
        executor = MigrationExecutor(connection)
        executor.migrate([before])
        try:
            apps = executor.loader.project_state([before]).apps
            users = apps.get_model("auth", "User").objects
            applicant = users.create(username="legacy-applicant")
            coach = users.create(username="legacy-coach")
            project = apps.get_model("standards", "SkillProject").objects.create(code="LEGACY", name="迁移项目")
            training_date = date(2026, 1, 1)
            cycle = apps.get_model("training", "TrainingCycle").objects.create(
                skill_project=project, code="LEGACY", name="迁移周期", start_date=training_date,
            )
            plan = apps.get_model("training", "TrainingPlan").objects.create(
                training_cycle=cycle, title="迁移计划", start_date=training_date, end_date=training_date,
                created_by=applicant,
            )
            changes = apps.get_model("training", "TrainingScheduleChange").objects
            values = {"training_plan": plan, "requested_by": applicant, "payload": [], "reason": "历史调整"}
            confirmed = {"user_id": applicant.pk, "decision": "approve", "note": "已同意", "at": timezone.now().isoformat()}
            unfinished = {"user_id": coach.pk, "decision": "", "note": "", "at": None}
            confirmations = [confirmed, unfinished]
            legacy = changes.create(**values, confirmations=confirmations)
            legacy.confirmation_users.add(applicant, coach)
            exempt_ids = [
                changes.create(**values, confirmations=[confirmed]).pk,
                changes.create(**values).pk,
                changes.create(**values, confirmations=confirmations, status="approved").pk,
                changes.create(**values, confirmations=confirmations, status="rejected").pk,
                changes.create(**values, confirmations=confirmations, consultation_confirmed_at=timezone.now()).pk,
            ]
            executor = MigrationExecutor(connection)
            executor.migrate([after])
            changes = executor.loader.project_state([after]).apps.get_model("training", "TrainingScheduleChange").objects
            converted = changes.get(pk=legacy.pk)
            self.assertEqual(converted.status, "pending")
            self.assertIsNotNone(converted.legacy_consultation_assumed_at)
            self.assertIsNone(converted.consultation_confirmed_at)
            self.assertEqual(converted.confirmations, confirmations)
            self.assertSetEqual(set(converted.confirmation_users.values_list("pk", flat=True)), {applicant.pk, coach.pk})
            self.assertFalse(changes.filter(pk__in=exempt_ids, legacy_consultation_assumed_at__isnull=False).exists())
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
