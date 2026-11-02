from datetime import date, datetime, time, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import process, scheduling
from .models import (
    PersonalTrainingTask,
    TrainingCycleMember,
    TrainingPeriodConfig,
    TrainingPlan,
    TrainingPlanParticipant,
    TrainingScheduleSlot,
    TrainingStateChange,
)
from .selectors import visible_training_tasks_for
from .tests import TrainingFixtureMixin, User


class ProcessFixture(TrainingFixtureMixin):
    def setUp(self):
        super().setUp()
        self.clock = patch("django.utils.timezone.now", return_value=datetime(2026, 1, 1, 0, tzinfo=dt_timezone.utc))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.cycle_obj = self.cycle()
        self.bind(self.cycle_obj)
        self.admin = User.objects.create_superuser("process-admin")
        self.coach = self.person("coach", "coach")
        self.other = self.person("other", "coach")
        self.student = self.person("student", "competitor")
        self.student2 = self.person("student2", "competitor")
        for period, start, end in [("early", 8, 9), ("morning", 9, 12), ("afternoon", 14, 17), ("evening", 19, 21)]:
            TrainingPeriodConfig.objects.update_or_create(period=period, defaults={"start_time": time(start), "end_time": time(end)})
        self.plan = TrainingPlan.objects.create(
            training_cycle=self.cycle_obj,
            title="测试计划",
            objective="测试",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
            created_by=self.admin,
        )
        self.plan.schedulers.add(self.coach)
        for user in (self.student, self.student2):
            TrainingPlanParticipant.objects.create(training_plan=self.plan, user=user, was_initial=True)
        scheduling.initialize_schedule(self.plan)
        self.plan.refresh_from_db()
        TrainingScheduleSlot.objects.filter(day__training_plan=self.plan).update(kind="unused")
        self.slot = self.plan.schedule_days.get(date=date(2026, 1, 1)).slots.get(period="morning")
        self.slot.kind, self.slot.primary_domain = "technical", self.linux
        self.slot.save()
        self.slot.domains.add(self.linux)
        self.slot.coaches.add(self.coach)
        self.plan.published_at = timezone.now()
        self.plan.save()
        for day in self.plan.schedule_days.all():
            day.duty_coaches.add(self.coach)
        scheduling.publish_schedule(self.plan, self.admin)
        self.plan.refresh_from_db()
        self.plan.published_at = timezone.now()
        self.plan.save()
        self.slot = TrainingScheduleSlot.objects.select_related("day__training_plan").get(pk=self.slot.pk)

    def person(self, username, role):
        user = User.objects.create_user(username)
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="training"))
        TrainingCycleMember.objects.create(training_cycle=self.cycle_obj, user=user, role=role)
        return user

    def task(self, **values):
        return scheduling.save_slot_task(self.slot, self.coach, {"title": "任务", **values}, publish=True)


class TrainingProcessTests(ProcessFixture, TestCase):
    def test_slot_editor_is_compact_and_cannot_target_another_day(self):
        self.client.force_login(self.admin)
        url = reverse("training:schedule_edit", args=[self.plan.pk])
        response = self.client.get(url, {"days": [self.slot.day_id], "slot": self.slot.pk}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["slot_forms"]), 1)
        self.assertEqual(len(response.context["day_forms"]), 0)
        other_day = self.plan.schedule_days.exclude(pk=self.slot.day_id).get()
        self.assertEqual(self.client.get(url, {"days": [other_day.pk], "slot": self.slot.pk}).status_code, 403)

    def test_time_configuration_is_in_plan_form_and_standalone_page_is_removed(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("training:plan_edit", args=[self.plan.pk]))
        self.assertContains(response, 'name="morning_start"')
        self.assertEqual(self.client.get("/training/period-config/").status_code, 404)
        TrainingPeriodConfig.objects.all().delete()
        # 已有计划使用自己的配置，不依赖全局表。
        scheduling.initialize_schedule(self.plan)

    def test_bulk_clear_confirmation_rechecks_time_even_for_empty_slots(self):
        from django.core import signing
        from .scheduling import day_snapshot, slot_snapshot

        self.client.force_login(self.admin)
        self.plan.schedule_published_at = None
        self.plan.status = "draft"
        self.plan.save()
        day = self.slot.day
        before = day_snapshot(day)
        payload = [{"type": "day", "id": day.pk, "revision": day.revision, "before": before, "after": before}]
        for slot in day.slots.all():
            before = slot_snapshot(slot)
            payload.append(
                {"type": "slot", "id": slot.pk, "revision": slot.revision, "before": before, "after": before}
            )
        token = signing.dumps({"user": self.admin.pk, "plan": self.plan.pk, "payload": payload}, salt="training.clear")
        with patch("django.utils.timezone.now", return_value=self.slot.ends_at):
            response = self.client.post(
                reverse("training:schedule_bulk", args=[self.plan.pk]), {"token": token}, HTTP_HX_REQUEST="true"
            )
        self.assertEqual(response.status_code, 403)
        self.slot.refresh_from_db()
        original = next(
            change["revision"] for change in payload if change["type"] == "slot" and change["id"] == self.slot.pk
        )
        self.assertEqual(self.slot.revision, original)

    def test_historical_snapshot_command_requires_explicit_confirmation(self):
        from io import StringIO
        from django.core.management import call_command
        from .models import TrainingScheduleSlot

        TrainingScheduleSlot.objects.filter(pk=self.slot.pk).update(starts_at=None, ends_at=None)
        call_command("snapshot_training_plan", self.plan.pk, actor=self.admin.pk, stdout=StringIO())
        self.slot.refresh_from_db()
        self.assertIsNone(self.slot.ends_at)
        call_command("snapshot_training_plan", self.plan.pk, actor=self.admin.pk, confirm=True, stdout=StringIO())
        self.slot.refresh_from_db()
        self.assertIsNotNone(self.slot.ends_at)
        before = self.slot.ends_at
        call_command("snapshot_training_plan", self.plan.pk, actor=self.admin.pk, confirm=True, stdout=StringIO())
        self.slot.refresh_from_db()
        self.assertEqual(before, self.slot.ends_at)
        self.assertEqual(self.plan.change_records.filter(action="补录历史时间快照").count(), 1)

    def test_legacy_plan_framework_is_only_generated_with_explicit_confirmation(self):
        from io import StringIO
        from django.core.management import call_command

        old = TrainingPlan.objects.create(
            training_cycle=self.cycle_obj,
            title="无框架的历史计划",
            **{name: getattr(self.plan, name) for name in TrainingPlan.TIME_FIELDS},
            objective="保留",
            start_date=self.plan.start_date,
            end_date=self.plan.end_date,
            created_by=self.admin,
        )
        call_command("snapshot_training_plan", old.pk, actor=self.admin.pk, stdout=StringIO())
        self.assertFalse(old.schedule_days.exists())
        call_command("snapshot_training_plan", old.pk, actor=self.admin.pk, confirm=True, stdout=StringIO())
        self.assertEqual(old.schedule_days.count(), 2)
        self.assertEqual(TrainingScheduleSlot.objects.filter(day__training_plan=old, ends_at__isnull=False).count(), 8)
        self.assertFalse(old.tasks.exists())

    def test_schedule_pagination_is_31_dates_and_clear_rechecks_signed_targets(self):
        from .models import TrainingCycle

        TrainingCycle.objects.filter(pk=self.cycle_obj.pk).update(end_date=date(2026, 3, 1))
        self.cycle_obj.refresh_from_db()
        longer = TrainingPlan.objects.create(
            training_cycle=self.cycle_obj,
            title="跨月计划",
            objective="分页",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 2),
            created_by=self.admin,
        )
        longer.schedulers.add(self.admin)
        scheduling.initialize_schedule(longer)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("training:plan_detail", args=[longer.pk]))
        self.assertEqual(response.context["page_obj"].paginator.per_page, 31)
        self.assertEqual(len(response.context["page_obj"].object_list), 31)
        response = self.client.get(reverse("training:plan_detail", args=[longer.pk]), {"page": 2})
        self.assertEqual(len(response.context["page_obj"].object_list), 2)
        day = longer.schedule_days.first()
        preview = self.client.get(
            reverse("training:schedule_bulk", args=[longer.pk]),
            {"days": [day.pk], "operation": "clear"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(preview.status_code, 403)
        self.assertEqual(day.slots.filter(kind="pending").count(), 4)

    def test_task_manager_has_no_definition_override_and_skill_exception_survives_lock(self):
        self.plan.task_managers.add(self.other)
        self.assertFalse(scheduling.can_fill(self.other, self.slot))
        task = self.task()
        with patch("django.utils.timezone.now", return_value=self.slot.ends_at):
            change = scheduling.set_task_skills(task, self.coach, [], reason="补正历史技能")
            self.assertEqual(change.status, "pending")
            scheduling.review_change(change, self.admin, approve=True)
            self.assertTrue(task.change_records.filter(action="保存任务").exists())

    def test_multiple_feedback_authors_never_overwrite(self):
        task = self.task()
        self.slot.coaches.add(self.other)
        execution = task.executions.get(user=self.student)
        process.add_feedback(execution, self.coach, "教练一")
        process.add_feedback(execution, self.other, "教练二")
        self.assertEqual(execution.feedback_records.count(), 2)
        with self.assertRaises(ValidationError):
            execution.feedback_records.update(content="覆盖")

    def test_explicit_publication_assigns_snapshot_and_hides_other_tasks(self):
        task = self.task(title="仅选手一可见的独立训练条目", assign_all=False, competitors=[self.student.pk])
        self.assertEqual(task.status, "published")
        self.assertTrue(task.executions.filter(user=self.student).exists())
        self.assertFalse(visible_training_tasks_for(self.student2).filter(pk=task.pk).exists())
        later = self.person("later", "competitor")
        self.assertFalse(task.executions.filter(user=later).exists())

    def test_time_boundary_requires_review_but_allows_execution_progress_feedback(self):
        task = self.task()
        execution = task.executions.get(user=self.student)
        with patch("django.utils.timezone.now", return_value=self.slot.ends_at):
            self.assertTrue(self.slot.is_locked)
            with self.assertRaises(ValidationError):
                scheduling.save_slot_task(self.slot, self.coach, {"title": "改写"}, task=task)
            with self.assertRaises(ValidationError):
                scheduling.assign_competitors(task, self.coach)
            with self.assertRaisesMessage(ValidationError, "撤回"):
                scheduling.cancel_task(task, self.coach, "申请取消")
            task.refresh_from_db()
            self.assertEqual(task.status, "published")
            process.change_state(execution, self.student, "completed")
            process.change_state(execution, self.student, "unfinished")
            progress = process.save_progress(execution, self.student, completed="配置完成", problems="待排错")
            process.save_progress(execution, self.student, completed="已修复", problems="", progress=progress)
            self.assertEqual(progress.revisions.get().completed, "配置完成")
            process.add_feedback(execution, self.coach, "建议检查日志")
            self.assertEqual(execution.feedback_records.count(), 1)
            self.assertEqual(TrainingStateChange.objects.count(), 2)

    def test_progress_prevents_revocation_and_reason_required(self):
        task = self.task()
        execution = task.executions.get(user=self.student)
        with self.assertRaisesMessage(ValidationError, "原因"):
            scheduling.assign_competitors(task, self.coach, selected=[self.student2.pk])
        process.save_progress(execution, self.student, completed="已查阅", problems="")
        with self.assertRaisesMessage(ValidationError, "开始"):
            scheduling.assign_competitors(task, self.coach, selected=[self.student2.pk], reason="调整")

    def test_personal_coach_scope_uses_assignment_history_and_does_not_affect_rate(self):
        task = self.task(assign_all=False, competitors=[self.student.pk])
        personal = process.save_personal_task(
            self.plan, self.student, {"title": "自主学习", "date": self.plan.start_date}
        )
        self.assertIn(personal, process.personal_tasks_for(self.coach))
        self.assertNotIn(personal, process.personal_tasks_for(self.other))
        with self.assertRaises(PermissionDenied):
            process.save_personal_task(self.plan, self.coach, {"title": "越权"}, task=personal)
        with self.assertRaises(PermissionDenied):
            process.add_feedback(personal, self.other, "越权")
        process.add_feedback(personal, self.coach, "鼓励自主学习")
        process.change_state(personal, self.student, "completed")
        with patch("django.utils.timezone.now", return_value=self.slot.ends_at):
            self.assertEqual(process.official_completion(self.plan)["total"], 1)
            self.assertEqual(process.official_completion(self.plan)["completed"], 0)
            process.change_state(task.executions.get(), self.student, "completed")
            self.assertEqual(process.official_completion(self.plan)["rate"], 1)
        self.assertEqual(PersonalTrainingTask.objects.count(), 1)

    def test_config_change_never_changes_existing_snapshots(self):
        before = self.slot.ends_at
        TrainingPeriodConfig.objects.filter(period="morning").update(end_time=time(13))
        scheduling.initialize_schedule(self.plan)
        self.slot.refresh_from_db()
        self.assertEqual(before, self.slot.ends_at)

    def test_single_domain_and_all_coaches_are_exclusive(self):
        values = scheduling.slot_snapshot(self.slot)
        with self.assertRaises(ValidationError):
            scheduling.validate_slot(self.plan, values | {"domains": [self.linux.pk, self.windows.pk]})
        values = values | {"coaches": [self.coach.pk]}
        scheduling.validate_slot(self.plan, values)
        self.assertNotIn("primary_coach", values)

    def test_http_schedule_task_lists_and_private_history(self):
        task = self.task(title="仅选手一可见的独立训练条目", assign_all=False, competitors=[self.student.pk])
        self.client.force_login(self.student2)
        response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, task.title + "</a>")
        self.assertNotContains(response, "变更历史")
        self.assertNotContains(response, "排班调整申请")
        self.assertEqual(self.client.get(reverse("training:task_detail", args=[task.pk])).status_code, 404)
        self.client.force_login(self.student)
        response = self.client.get(reverse("training:execution_detail", args=[task.executions.get().pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "追加训练进度")
        response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]), {"tab": "tasks"})
        self.assertContains(response, task.title)

    def test_http_personal_task_form_and_coach_feedback(self):
        self.task()
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("training:personal_create", args=[self.plan.pk]),
            {"date": "2026-01-02", "title": "自主排错", "period": "", "description": "**实践**"},
        )
        self.assertEqual(response.status_code, 302)
        task = PersonalTrainingTask.objects.get()
        self.client.force_login(self.coach)
        response = self.client.post(
            reverse("training:personal_detail", args=[task.pk]),
            {"action": "feedback", "content": "建议复现"},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, "建议复现")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("training:personal_detail", args=[task.pk])).status_code, 404)
