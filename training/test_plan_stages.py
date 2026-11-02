from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch
from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from . import scheduling
from .change_workflow import review, swap_schedule
from .forms import TrainingPlanForm
from .models import TrainingPlan, TrainingScheduleChange, TrainingScheduleSlot
from .process import change_state, visible_target
from .selectors import visible_training_tasks_for
from .test_process_refactor import ProcessFixture


class PlanStagesTests(ProcessFixture, TestCase):
    def setUp(self):
        super().setUp()

    def publish_plan(self):
        self.plan.published_at = timezone.now()
        self.plan.save()

    def values(self, **overrides):
        return {"training_cycle": self.cycle_obj.pk, "title": self.plan.title,
                "start_date": self.plan.start_date.isoformat(), "end_date": self.plan.end_date.isoformat(),
                "objective": self.plan.objective, "schedulers": [self.coach.pk],
                "competitors": [self.student.pk, self.student2.pk],
                **{name: getattr(self.plan, name).isoformat() for name in TrainingPlan.TIME_FIELDS}, **overrides}

    def test_task_publication_is_individual_and_all_three_gates_apply(self):
        draft = scheduling.save_slot_task(self.slot, self.coach, {"title": "未发布的秘密任务"})
        live = scheduling.save_slot_task(self.slot, self.coach, {"title": "已发布的任务"}, publish=True)
        self.assertEqual(draft.status, "draft")
        self.assertFalse(draft.executions.exists())
        self.assertTrue(visible_training_tasks_for(self.student).exists())
        self.assertTrue(visible_target(self.student, live.executions.get(user=self.student)))
        self.publish_plan()
        self.assertEqual(list(visible_training_tasks_for(self.student)), [live])
        live.refresh_from_db()
        self.assertTrue(visible_target(self.student, live.executions.get(user=self.student)))
        self.plan.schedule_published_at = None
        self.plan.save()
        self.assertFalse(visible_training_tasks_for(self.student).exists())

    def test_plan_form_mixed_layout_and_no_status_choice(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("training:plan_edit", args=[self.plan.pk]))
        self.assertNotIn("status", response.context["form"].fields)
        self.assertContains(response, 'name="action" value="publish"')
        self.assertContains(response, 'grid gap-4 md:grid-cols-2')
        self.assertFalse(response.context["form"].fields["early_start"].required)
        self.assertTrue(response.context["form"].fields["morning_start"].required)
        form = TrainingPlanForm(self.values(morning_end="08:00"), instance=self.plan)
        self.assertFalse(form.is_valid())

    def test_plan_publication_does_not_publish_schedule_and_dates_stay_fixed(self):
        self.plan.schedule_published_at = None
        self.plan.save()
        form = TrainingPlanForm(self.values(), instance=self.plan)
        self.assertTrue(form.is_valid(), form.errors)
        plan = scheduling.save_plan_definition(form, self.admin, publish=True)
        self.assertIsNotNone(plan.published_at)
        self.assertIsNone(plan.schedule_published_at)
        form = TrainingPlanForm(self.values(start_date="2026-01-02"), instance=plan)
        self.assertFalse(form.is_valid())

    def test_draft_schedule_blocks_task_filling(self):
        self.plan.schedule_published_at = None
        self.plan.save()
        self.slot.day.training_plan = self.plan
        with self.assertRaises(PermissionDenied):
            scheduling.save_slot_task(self.slot, self.coach, {"title": "不得提前填写"})

    def test_future_task_edits_are_immediate_and_audited(self):
        task = scheduling.save_slot_task(self.slot, self.coach, {"title": "原内容"}, publish=True)
        scheduling.save_slot_task(self.slot, self.coach, {"title": "更新内容"}, task=task)
        task.refresh_from_db()
        self.assertEqual(task.title, "更新内容")
        self.assertFalse(self.plan.schedule_changes.exists())
        record = task.change_records.filter(action="保存任务").first()
        self.assertEqual(record.before["title"], "原内容")
        self.assertEqual(record.after["title"], "更新内容")

    def test_expired_task_needs_review_preserving_execution(self):
        task = scheduling.save_slot_task(self.slot, self.coach, {"title": "原内容"}, publish=True)
        execution = task.executions.get(user=self.student)
        self.publish_plan()
        change_state(execution, self.student, "in_progress")
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 3, tzinfo=dt_timezone.utc)):
            change = scheduling.save_slot_task(self.slot, self.coach, {"title": "补正内容", "reason": "实际已经执行，补记"}, task=task)
            self.assertIsInstance(change, TrainingScheduleChange)
            task.refresh_from_db()
            self.assertEqual(task.title, "原内容")
            self.assertEqual(change.confirmations, [])
            review(change, self.admin, approve=True)
            task.refresh_from_db()
            execution.refresh_from_db()
            self.assertEqual(task.title, "补正内容")
            self.assertEqual(execution.status, "in_progress")
            self.assertEqual(task.executions.get(user=self.student).pk, execution.pk)

    def test_coaches_confirm_in_order_before_final_review(self):
        self.plan.approvers.add(self.other)
        before = scheduling.slot_snapshot(self.slot)
        payload = [{"type": "slot", "id": self.slot.pk, "revision": self.slot.revision, "before": before,
                    "after": before | {"coaches": [self.other.pk]}}]
        change = scheduling.save_schedule(self.plan, self.admin, payload, "交接负责教练")
        with self.assertRaises(PermissionDenied):
            review(change, self.admin, approve=True)
        review(change, self.coach, approve=True)
        review(change, self.other, approve=True)
        self.slot.refresh_from_db()
        self.assertIn(self.coach.pk, self.slot.coaches.values_list("pk", flat=True))
        review(change, self.other, approve=True)  # 同一人须另外履行终审职责。
        self.slot.refresh_from_db()
        self.assertIn(self.other.pk, self.slot.coaches.values_list("pk", flat=True))
        with self.assertRaises(ValidationError):
            review(change, self.other, approve=True)

    def test_expired_swap_is_temporarily_disabled(self):
        with self.assertRaises(ValidationError):
            swap_schedule(self.plan, self.coach, self.slot.day_id, self.plan.schedule_days.last().pk, ["morning"], True, "调班")

    def test_stale_request_does_not_overwrite_task(self):
        task = scheduling.save_slot_task(self.slot, self.coach, {"title": "原内容"}, publish=True)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 3, tzinfo=dt_timezone.utc)):
            first = scheduling.save_slot_task(self.slot, self.coach, {"title": "第一份", "reason": "补记"}, task=task)
            second = scheduling.save_slot_task(self.slot, self.coach, {"title": "第二份", "reason": "补记"}, task=task)
            review(first, self.admin, approve=True)
            with self.assertRaises(ValidationError):
                review(second, self.admin, approve=True)

    def test_future_times_require_coach_confirmation_and_preserve_history(self):
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 1, 6, tzinfo=dt_timezone.utc)):
            form = TrainingPlanForm(self.values(morning_start="09:30", reason="调整未来作息"), instance=self.plan)
            self.assertTrue(form.is_valid(), form.errors)
            scheduling.save_plan_definition(form, self.admin)
            change = self.plan.schedule_changes.latest("pk")
            while True:
                change.refresh_from_db()
                pending = next((step for step in change.confirmations if not step["decision"]), None)
                if not pending:
                    break
                from django.contrib.auth import get_user_model
                review(change, get_user_model().objects.get(pk=pending["user_id"]), approve=True)
            review(change, self.admin, approve=True)
            self.slot.refresh_from_db()
            future = TrainingScheduleSlot.objects.get(day__training_plan=self.plan, day__date="2026-01-02", period="morning")
            self.assertEqual(timezone.localtime(self.slot.starts_at).strftime("%H:%M"), "09:00")
            self.assertEqual(timezone.localtime(future.starts_at).strftime("%H:%M"), "09:30")

    def test_rejected_change_never_updates_original_content(self):
        before = scheduling.slot_snapshot(self.slot)
        payload = [{"type": "slot", "id": self.slot.pk, "revision": self.slot.revision, "before": before,
                    "after": before | {"coaches": [self.other.pk]}}]
        change = scheduling.save_schedule(self.plan, self.admin, payload, "申请交接")
        review(change, self.coach, approve=False, note="仍按原安排")
        change.refresh_from_db()
        self.slot.refresh_from_db()
        self.assertEqual(change.status, "rejected")
        self.assertIn(self.coach.pk, self.slot.coaches.values_list("pk", flat=True))
        self.assertEqual(change.confirmations[0]["decision"], "reject")

    def test_new_responsible_coach_can_view_and_confirm_request_before_handoff(self):
        before = scheduling.slot_snapshot(self.slot)
        payload = [{"type": "slot", "id": self.slot.pk, "revision": self.slot.revision, "before": before,
                    "after": before | {"coaches": [self.other.pk]}}]
        change = scheduling.save_schedule(self.plan, self.coach, payload, "交接给另一位教练")
        self.client.force_login(self.other)
        response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("training:schedule_review", args=[change.pk]))

    def test_empty_and_unpublished_task_cells_are_blank_for_student(self):
        self.publish_plan()
        self.client.force_login(self.student)
        response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
        table = response.context["table"]
        row = next(row for row in table.rows if row.record.pk == self.slot.day_id)
        self.assertEqual(row.get_cell("morning"), "")
        scheduling.save_slot_task(self.slot, self.coach, {"title": "不可见草稿"})
        response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
        self.assertNotContains(response, "不可见草稿")

    def test_schedule_publication_rejects_unfilled_days(self):
        self.plan.schedule_published_at = None
        self.plan.save()
        self.plan.schedule_days.exclude(pk=self.slot.day_id).get().slots.update(kind="pending")
        with self.assertRaises(ValidationError):
            scheduling.publish_schedule(self.plan, self.coach)

    def test_expired_new_task_and_attachment_stay_private_until_review(self):
        with TemporaryDirectory() as directory, override_settings(PRIVATE_MEDIA_ROOT=directory):
            self.publish_plan()
            with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 3, tzinfo=dt_timezone.utc)):
                from .change_workflow import request_task_change
                change = request_task_change(self.plan, self.slot, None, self.coach, {"title": "补录历史任务", "reason": "已线下完成，补录", "attachments": [SimpleUploadedFile("指导.txt", b"private guide")]}, True)
                self.assertFalse(self.plan.tasks.exists())
                attachment = change.attachments.get()
                url = reverse("training:attachment_download", args=["change", attachment.pk])
                self.client.force_login(self.student)
                self.assertEqual(self.client.get(url).status_code, 403)
                self.client.force_login(self.admin)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                response.close()
                review(change, self.admin, approve=True)
                task = self.plan.tasks.get()
                self.assertEqual(task.status, "published")
                self.assertEqual(task.executions.count(), 2)
                self.assertEqual(task.attachments.get().original_filename, "指导.txt")
                self.assertEqual(self.client.get(reverse("training:task_detail", args=[task.pk])).status_code, 200)

    def test_plan_times_are_independent(self):
        values = self.values(title="另一个计划", morning_start="09:30")
        form = TrainingPlanForm(values)
        self.assertTrue(form.is_valid(), form.errors)
        other = scheduling.save_plan_definition(form, self.admin)
        self.assertEqual(other.morning_start.strftime("%H:%M"), "09:30")
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.morning_start.strftime("%H:%M"), "09:00")

    def test_completed_display_does_not_publish_or_block_corrections(self):
        self.plan.published_at = None
        self.plan.save()
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 3, tzinfo=dt_timezone.utc)):
            self.assertEqual(self.plan.display_status, "已完成")
            self.assertIsNone(self.plan.published_at)
            self.assertFalse(scheduling.visible_plans(self.student).exists())
            self.publish_plan()
            change = scheduling.save_slot_task(self.slot, self.coach, {"title": "补记", "reason": "补记实际训练"})
            self.assertEqual(change.status, "draft")
            self.assertFalse(self.plan.schedule_changes.exists())

    def test_explicit_time_configuration_fills_unknown_future_slots_only(self):
        self.plan.schedule_published_at = None
        self.plan.save()
        TrainingScheduleSlot.objects.filter(day__training_plan=self.plan).update(starts_at=None, ends_at=None)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 1, 6, tzinfo=dt_timezone.utc)):
            form = TrainingPlanForm(self.values(morning_start="09:30"), instance=self.plan)
            self.assertTrue(form.is_valid(), form.errors)
            scheduling.save_plan_definition(form, self.admin)
            self.slot.refresh_from_db()
            future = TrainingScheduleSlot.objects.get(day__training_plan=self.plan, day__date="2026-01-02", period="morning")
            self.assertIsNone(self.slot.ends_at)
            self.assertEqual(timezone.localtime(future.starts_at).strftime("%H:%M"), "09:30")

    def test_designated_ordinary_approver_can_review_expired_task(self):
        self.plan.approvers.add(self.other)
        task = scheduling.save_slot_task(self.slot, self.coach, {"title": "原任务"}, publish=True)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 3, tzinfo=dt_timezone.utc)):
            change = scheduling.save_slot_task(self.slot, self.coach, {"title": "历史补记", "reason": "已完成，补录"}, task=task)
            review(change, self.other, approve=True)
            self.assertEqual(self.plan.tasks.get().title, "历史补记")

    def test_attachment_copy_is_cleaned_if_final_audit_fails(self):
        from pathlib import Path
        from .models import TrainingChangeRecord
        with TemporaryDirectory() as directory, override_settings(PRIVATE_MEDIA_ROOT=directory):
            with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 3, tzinfo=dt_timezone.utc)):
                from .change_workflow import request_task_change
                change = request_task_change(self.plan, self.slot, None, self.coach, {"title": "补记", "reason": "实际执行补记", "attachments": [SimpleUploadedFile("指导.txt", b"guide")]}, False)
                before = {path for path in Path(directory).rglob("*") if path.is_file()}
                original = TrainingChangeRecord.objects.create

                def fail_final_audit(**kwargs):
                    if kwargs["action"] == "批准调整":
                        raise RuntimeError("审计写入失败")
                    return original(**kwargs)

                with patch.object(TrainingChangeRecord.objects, "create", side_effect=fail_final_audit), self.assertRaises(RuntimeError):
                    review(change, self.admin, approve=True)
                self.assertFalse(self.plan.tasks.exists())
                self.assertEqual({path for path in Path(directory).rglob("*") if path.is_file()}, before)
                change.refresh_from_db()
                self.assertEqual(change.status, "pending")
