from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TrainingProcessMigrationTests(TransactionTestCase):
    def test_preserves_legacy_execution_feedback_attachments_and_unknown_time(self):
        before = ("training", "0010_alter_trainingplan_options_trainingplan_approvers_and_more")
        executor = MigrationExecutor(connection)
        executor.migrate([before])
        try:
            apps = executor.loader.project_state([before]).apps
            User = apps.get_model("auth", "User")
            student = User.objects.create(username="migration-student")
            coach = User.objects.create(username="migration-coach")
            project = apps.get_model("standards", "SkillProject").objects.create(code="PROCESS", name="迁移项目")
            cycle = apps.get_model("training", "TrainingCycle").objects.create(
                skill_project=project, code="PROCESS", name="迁移周期", start_date=date(2026, 1, 1)
            )
            plan = apps.get_model("training", "TrainingPlan").objects.create(
                training_cycle=cycle,
                title="原计划",
                objective="原目标",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 2),
                created_by=coach,
            )
            day = apps.get_model("training", "TrainingScheduleDay").objects.create(
                training_plan=plan, date=date(2026, 1, 1)
            )
            slot = apps.get_model("training", "TrainingScheduleSlot").objects.create(day=day, period="morning")
            task = apps.get_model("training", "TrainingTask").objects.create(
                training_plan=plan, schedule_slot=slot, title="原任务", planned_date=day.date, created_by=coach
            )
            apps.get_model("training", "TrainingTaskCoach").objects.create(
                training_task=task, user=coach, role="primary"
            )
            execution = apps.get_model("training", "TaskExecution").objects.create(
                training_task=task,
                user=student,
                status="blocked",
                completion_note="完成内容",
                problems="阻塞问题",
                coach_feedback="原反馈",
                feedback_by=coach,
            )
            attachment = apps.get_model("training", "TaskExecutionAttachment").objects.create(
                task_execution=execution, file="legacy/原附件.pdf", original_filename="原附件.pdf", uploaded_by=student
            )
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
            apps = executor.loader.project_state().apps
            migrated = apps.get_model("training", "TaskExecution").objects.get(pk=execution.pk)
            self.assertEqual(
                (migrated.status, migrated.legacy_status, migrated.training_task_id), ("blocked", "blocked", task.pk)
            )
            self.assertEqual(
                apps.get_model("training", "TrainingProgress").objects.get(execution=migrated).completed, "完成内容"
            )
            self.assertEqual(
                apps.get_model("training", "TrainingCoachFeedback").objects.get(execution=migrated).author_id, coach.pk
            )
            self.assertEqual(
                apps.get_model("training", "TaskExecutionAttachment").objects.get(pk=attachment.pk).file.name,
                "legacy/原附件.pdf",
            )
            self.assertIsNone(apps.get_model("training", "TrainingScheduleSlot").objects.get(pk=slot.pk).ends_at)
            participant = apps.get_model("training", "TrainingPlanParticipant").objects.get(
                training_plan_id=plan.pk, user_id=student.pk
            )
            self.assertFalse(participant.was_initial)
            self.assertFalse(participant.is_active)
            self.assertEqual(
                apps.get_model("training", "TrainingAssignmentCoach").objects.get(execution_id=execution.pk).user_id,
                coach.pk,
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
