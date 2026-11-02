from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from . import plan_publish, scheduling
from .models import TrainingTask
from .test_process_refactor import ProcessFixture


class PlanPublishTests(ProcessFixture, TestCase):
    def draft(self, title, **values):
        return scheduling.save_slot_task(self.slot, self.coach, {"title": title, **values})

    def test_preview_and_publish_preserve_task_allocation_and_skip_other_states(self):
        first = self.draft("全体训练")
        second = self.draft("指定选手", assign_all=False, competitors=[self.student.pk])
        published = self.task(title="已经发布")
        removed = self.draft("已经取消")
        scheduling.cancel_task(removed, self.coach, "不再需要")
        before = self.plan.change_records.count()
        result = plan_publish.preview(self.plan, self.admin)
        self.assertEqual(self.plan.change_records.count(), before)
        self.assertFalse(first.executions.exists())
        self.assertEqual({row["task"].pk for row in result["rows"]}, {first.pk, second.pk})
        self.assertEqual({person[0] for person in result["rows"][0]["people"]}, {self.student.pk, self.student2.pk})
        self.assertTrue(result["can_confirm"])
        plan_publish.publish(self.plan, self.admin, result["digest"])
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "published")
        self.assertEqual(second.status, "published")
        self.assertEqual(set(second.executions.values_list("user_id", flat=True)), {self.student.pk})
        self.assertEqual(published.status, "published")
        self.assertTrue(first.change_records.filter(action="发布任务").exists())

    def test_invalid_task_blocks_all_and_legacy_task_is_reported(self):
        valid = self.draft("可发布")
        legacy = TrainingTask.objects.create(training_plan=self.plan, planned_date=self.plan.start_date,
                                             title="历史草稿", created_by=self.admin)
        result = plan_publish.preview(self.plan, self.admin)
        self.assertFalse(result["can_confirm"])
        self.assertIn("没有所属时段", next(row["error"] for row in result["rows"] if row["task"].pk == legacy.pk))
        with self.assertRaises(ValidationError):
            plan_publish.publish(self.plan, self.admin, result["digest"])
        valid.refresh_from_db()
        self.assertEqual(valid.status, "draft")
        self.assertFalse(valid.executions.exists())

    def test_membership_changes_invalidate_preview(self):
        self.draft("任务")
        result = plan_publish.preview(self.plan, self.admin)
        self.plan.participants.filter(user=self.student).update(is_active=False)
        with self.assertRaisesMessage(ValidationError, "重新预览"):
            plan_publish.publish(self.plan, self.admin, result["digest"])
        self.assertFalse(self.plan.tasks.filter(status="published").exists())

    def test_failed_commit_rolls_back_every_task(self):
        first = self.draft("第一项")
        second = self.draft("第二项")
        result = plan_publish.preview(self.plan, self.admin)
        original = scheduling.publish_slot_task
        calls = 0

        def fail_second(task, user, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise ValidationError("写入失败")
            return original(task, user, **kwargs)

        with patch("training.plan_publish.scheduling.publish_slot_task", side_effect=fail_second):
            with self.assertRaisesMessage(ValidationError, "写入失败"):
                plan_publish.publish(self.plan, self.admin, result["digest"])
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.status, second.status), ("draft", "draft"))
        self.assertFalse(first.executions.exists())

    def test_permissions_and_page_confirmation(self):
        self.draft("待发布任务")
        self.slot.coaches.add(self.other)
        with self.assertRaises(PermissionDenied):
            plan_publish.preview(self.plan, self.other)
        self.client.force_login(self.admin)
        url = reverse("training:publish_all_tasks", args=[self.plan.pk])
        preview = self.client.get(url)
        self.assertContains(preview, "待发布任务")
        self.assertContains(preview, "确认发布全部任务")
        response = self.client.post(url, {"token": preview.context["token"]})
        self.assertRedirects(response, reverse("training:plan_detail", args=[self.plan.pk]))
        self.assertTrue(self.plan.tasks.filter(status="published", title="待发布任务").exists())

    def test_scheduler_can_publish_and_preview_reports_empty_assignment(self):
        self.draft("草稿任务")
        result = plan_publish.preview(self.plan, self.coach)
        self.assertTrue(result["can_confirm"])
        self.plan.participants.update(is_active=False)
        result = plan_publish.preview(self.plan, self.coach)
        self.assertFalse(result["can_confirm"])
        self.assertIn("至少选择一名选手", result["rows"][0]["error"])

    def test_new_draft_invalidates_preview(self):
        self.draft("原任务")
        result = plan_publish.preview(self.plan, self.admin)
        self.draft("后来新增")
        with self.assertRaisesMessage(ValidationError, "重新预览"):
            plan_publish.publish(self.plan, self.admin, result["digest"])
        self.assertFalse(self.plan.tasks.filter(status="published").exists())

    def test_expired_draft_keeps_fixed_competitor_snapshot(self):
        task = self.draft("固定名单", assign_all=False, competitors=[self.student.pk])
        self.plan.participants.filter(user=self.student).update(is_active=False)
        with patch("django.utils.timezone.now", return_value=self.slot.ends_at):
            result = plan_publish.preview(self.plan, self.admin)
            self.assertEqual([person[0] for person in result["rows"][0]["people"]], [self.student.pk])
            plan_publish.publish(self.plan, self.admin, result["digest"])
        task.refresh_from_db()
        self.assertEqual(task.status, "published")
        self.assertEqual(list(task.executions.values_list("user_id", flat=True)), [self.student.pk])
