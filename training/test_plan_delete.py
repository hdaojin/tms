from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import scheduling
from .log_exemptions import ACTIONS
from .models import TrainingChangeRecord, TrainingPlan, TrainingTask, TrainingTaskAttachment
from .tests import TrainingFixtureMixin


class PlanDeleteTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        users = get_user_model().objects
        self.admin = users.create_superuser("admin")
        self.member = users.create_user("member")
        self.plan = TrainingPlan.objects.create(
            training_cycle=self.cycle(), title="日期有误", created_by=self.admin,
            start_date=date(2026, 1, 2), end_date=date(2026, 1, 2),
            objective="练习网络配置",
        )
        self.plan.participants.create(user=self.member)
        self.plan.training_cycle.members.create(user=self.member, role="competitor")
        scheduling.initialize_schedule(self.plan)
        self.plan.refresh_from_db()
        self.task = TrainingTask.objects.create(
            training_plan=self.plan, title="任务草稿", created_by=self.admin,
            planned_date=self.plan.start_date, schedule_slot=self.plan.schedule_days.get().slots.first(),
        )
        scheduling.audit(self.plan, self.admin, "保存任务", task=self.task)
        self.url = reverse("training:plan_delete", args=[self.plan.pk])
        self.detail = reverse("training:plan_detail", args=[self.plan.pk])
        self.client.force_login(self.admin)

    def test_preview_and_delete_draft_with_related_records_and_file(self):
        attachment = TrainingTaskAttachment.objects.create(
            training_task=self.task, file="draft.txt", uploaded_by=self.admin,
        )
        self.assertContains(self.client.get(self.detail), self.url)
        preview = self.client.get(self.url)
        self.assertContains(preview, "计划名单涉及 1 人")
        self.assertContains(preview, "1 天排班、1 项草稿任务")
        self.assertTrue(TrainingPlan.objects.filter(pk=self.plan.pk).exists())
        storage = attachment.file.storage
        with patch.object(storage, "exists", return_value=True), patch.object(storage, "delete") as delete:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url, {"token": preview.context["token"]})
            delete.assert_called_once_with("draft.txt")
        self.assertRedirects(response, reverse("training:plan_list"), fetch_redirect_response=False)
        self.assertFalse(TrainingPlan.objects.filter(pk=self.plan.pk).exists())
        self.assertFalse(TrainingTask.objects.filter(pk=self.task.pk).exists())

    def test_ordinary_user_with_delete_permission_is_denied(self):
        self.member.user_permissions.add(Permission.objects.get(codename="delete_trainingplan"))
        token = self.client.get(self.url).context["token"]
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {"token": token}).status_code, 403)

    def test_stale_preview_requires_new_confirmation(self):
        token = self.client.get(self.url).context["token"]
        self.plan.title = "已修改"
        self.plan.save()
        response = self.client.post(self.url, {"token": token})
        self.assertContains(response, "计划内容已变化")
        self.assertTrue(TrainingPlan.objects.filter(pk=self.plan.pk).exists())

    def test_current_publication_blocks_delete_but_withdrawn_plan_can_be_deleted(self):
        token = self.client.get(self.url).context["token"]
        self.plan.published_at = timezone.now()
        self.plan.save()
        published = scheduling.audit(self.plan, self.admin, "发布计划")
        self.assertContains(self.client.post(self.url, {"token": token}), "仅可删除计划和排班均未发布")
        self.plan.schedule_published_at = timezone.now()
        self.plan.published_at = None
        self.plan.save()
        self.assertContains(self.client.get(self.url), "仅可删除计划和排班均未发布")
        self.plan.schedule_published_at = None
        self.plan.save()
        scheduling.audit(self.plan, self.admin, "发布排班")
        scheduling.audit(self.plan, self.admin, "撤回发布", after={"层级": "schedule"})
        withdrawn = scheduling.audit(self.plan, self.admin, "撤回发布", after={"层级": "plan"}, reason="计划建错")
        self.assertContains(self.client.post(self.url, {"token": token}), "计划内容已变化")
        self.assertContains(self.client.get(self.detail), self.url)
        preview = self.client.get(self.url)
        self.assertContains(preview, "保留 4 条发布与撤回记录")
        response = self.client.post(self.url, {"token": preview.context["token"]})
        self.assertRedirects(response, reverse("training:plan_list"), fetch_redirect_response=False)
        self.assertFalse(TrainingPlan.objects.filter(pk=self.plan.pk).exists())
        history = TrainingChangeRecord.objects.filter(deleted_plan__id=self.plan.pk)
        self.assertEqual(history.count(), 5)
        original = history.get(pk=published.pk)
        self.assertIsNone(original.training_plan_id)
        self.assertEqual(original.created_at, published.created_at)
        self.assertEqual(original.actor_id, self.admin.pk)
        self.assertEqual(original.deleted_plan["title"], self.plan.title)
        self.assertEqual(history.get(pk=withdrawn.pk).reason, "计划建错")
        self.assertEqual(history.get(action="删除训练计划").actor_id, self.admin.pk)

    def test_unclassified_withdrawal_remains_protected(self):
        scheduling.audit(self.plan, self.admin, "撤回发布")
        self.assertContains(self.client.get(self.url), "已有受保护的历史记录")

    def test_draft_deletion_preserves_log_exemption_history(self):
        self.member.first_name = "选手甲"
        self.member.save(update_fields=["first_name"])
        url = reverse("training:plan_log_exemptions", args=[self.plan.pk])
        self.assertContains(self.client.get(self.detail), url)
        preview = self.client.post(url, {
            "operation": "add", "user": self.member.pk, "start": self.plan.start_date, "reason": "测试免交",
        })
        self.assertRedirects(self.client.post(url, {"token": preview.context["token"]}), url)
        self.assertContains(self.client.get(url), "测试免交")
        self.assertNotContains(self.client.get(self.detail), "测试免交")
        preview = self.client.get(self.url)
        self.assertContains(preview, "保留 1 条日志免交变更记录")
        response = self.client.post(self.url, {"token": preview.context["token"]})
        self.assertRedirects(response, reverse("training:plan_list"), fetch_redirect_response=False)
        record = TrainingChangeRecord.objects.get(deleted_plan__id=self.plan.pk, action=ACTIONS["add"])
        self.assertEqual(record.after["rule"]["user_ids"], [self.member.pk])
        self.assertEqual(record.reason, "测试免交")

    def test_task_withdrawal_remains_protected(self):
        scheduling.audit(self.plan, self.admin, "撤回发布", after={"层级": "task"}, task=self.task)
        self.assertContains(self.client.get(self.url), "已有受保护的历史记录")

    def test_task_assignment_after_preview_blocks_delete(self):
        token = self.client.get(self.url).context["token"]
        self.task.executions.create(user=self.member)
        self.assertContains(self.client.post(self.url, {"token": token}), "计划已有任务分配")
        self.assertTrue(self.task.executions.filter(user=self.member).exists())
