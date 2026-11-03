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
from .models import TrainingPlan, TrainingScheduleChange
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
                "responsible_coaches": list(self.plan.responsible_coaches.values_list("pk", flat=True)),
                "duty_personnel": list(self.plan.duty_personnel.values_list("pk", flat=True)),
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
        self.assertNotIn("responsible_coaches", response.context["form"].fields)
        self.assertNotIn("duty_personnel", response.context["form"].fields)
        self.assertTrue(response.context["form"].fields["morning_start"].disabled)
        self.assertContains(response, 'grid gap-4 md:grid-cols-2')
        self.assertFalse(response.context["form"].fields["early_start"].required)
        self.assertFalse(response.context["form"].fields["morning_start"].required)
        form = TrainingPlanForm(self.values(morning_end="08:00"))
        self.assertFalse(form.is_valid())

    def test_published_plan_ignores_forged_structure_changes(self):
        self.client.force_login(self.admin)
        url = reverse("training:plan_edit", args=[self.plan.pk])
        response = self.client.post(url, self.values(title="允许编辑", morning_start="09:30", start_date="2026-01-02"))
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.title, "允许编辑")
        self.assertEqual(self.plan.morning_start.strftime("%H:%M"), "09:00")
        self.assertEqual(self.plan.start_date.isoformat(), "2026-01-01")
        self.assertFalse(self.plan.schedule_changes.exists())

    def test_plan_publication_does_not_publish_schedule_and_dates_stay_fixed(self):
        self.plan.published_at = self.plan.schedule_published_at = None
        self.plan.save()
        form = TrainingPlanForm(self.values(), instance=self.plan)
        self.assertTrue(form.is_valid(), form.errors)
        plan = scheduling.publish_plan(self.plan, self.admin)
        self.assertIsNotNone(plan.published_at)
        self.assertIsNone(plan.schedule_published_at)
        form = TrainingPlanForm(self.values(start_date="2026-01-02"), instance=plan)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["start_date"].isoformat(), "2026-01-01")

    def test_plan_requires_three_rosters_and_duty_is_cycle_coach(self):
        self.plan.published_at = self.plan.schedule_published_at = None
        self.plan.save()
        self.plan.duty_personnel.clear()
        form = TrainingPlanForm(self.values(), instance=self.plan)
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaisesMessage(ValidationError, "每类至少一人"):
            scheduling.publish_plan(self.plan, self.admin)
        self.plan.refresh_from_db()
        self.assertIsNone(self.plan.published_at)
        from .plan_members import save_roster
        with self.assertRaises(ValidationError):
            save_roster(self.admin, self.plan, "duty_personnel", {self.coach.pk, self.student.pk})
        save_roster(self.admin, self.plan, "duty_personnel", {self.coach.pk})
        form = TrainingPlanForm(self.values(), instance=self.plan)
        self.assertTrue(form.is_valid(), form.errors)
        plan = scheduling.publish_plan(self.plan, self.admin)
        self.assertEqual(scheduling.duty_ids(plan), {self.coach.pk})
        self.assertFalse(scheduling.can_schedule(self.student, plan))
        day = plan.schedule_days.first()
        values = scheduling.day_snapshot(day)
        with self.assertRaisesMessage(ValidationError, "值班名单"):
            scheduling.validate_day(plan, values | {"duty_coaches": [self.student.pk]})
        with self.assertRaisesMessage(ValidationError, "值班名单"):
            scheduling.validate_day(plan, values | {"duty_coaches": [self.other.pk]})
        with self.assertRaisesMessage(ValidationError, "相关排班"):
            scheduling.check_roster_removal(plan, "duty_personnel", {self.coach.pk})

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

    def test_all_duty_approval_rechecks_roster(self):
        day = self.slot.day
        before = scheduling.day_snapshot(day)
        change = scheduling.save_schedule(self.plan, self.admin, [{
            "type": "day", "id": day.pk, "revision": day.revision, "before": before,
            "after": before | {"duty_all": True, "duty_coaches": []},
        }], "安排全员值班")
        self.confirm_change_coaches(change)
        self.plan.duty_personnel.add(self.student)
        with self.assertRaisesMessage(ValidationError, "计划人员名单已变化"):
            review(change, self.admin, approve=True)
        day.refresh_from_db()
        self.assertEqual(scheduling.day_snapshot(day), before)

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

    def test_published_time_change_cannot_bypass_form(self):
        from datetime import time

        self.plan.morning_start = time(9, 30)
        with self.assertRaisesMessage(ValidationError, "请先撤回计划发布"):
            self.plan.save(update_fields=["morning_start"])

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

    def test_publish_from_detail_requires_rosters_and_keeps_schedule_unpublished(self):
        self.plan.published_at = self.plan.schedule_published_at = None
        self.plan.save()
        self.client.force_login(self.admin)
        detail = reverse("training:plan_detail", args=[self.plan.pk])
        publish = reverse("training:plan_publish", args=[self.plan.pk])
        self.assertContains(self.client.get(detail), "发布计划")
        self.assertEqual(self.client.get(publish).status_code, 405)
        self.plan.duty_personnel.clear()
        self.client.post(publish)
        self.plan.refresh_from_db()
        self.assertIsNone(self.plan.published_at)
        self.plan.duty_personnel.add(self.coach)
        self.assertRedirects(self.client.post(publish), detail)
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.published_at)
        self.assertIsNone(self.plan.schedule_published_at)
        self.assertContains(self.client.get(detail), "撤回计划")

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
