from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import scheduling
from .models import TrainingPlan, TrainingTask, TrainingTaskAttachment
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

    def test_publication_after_preview_and_withdrawal_both_block_delete(self):
        token = self.client.get(self.url).context["token"]
        self.plan.published_at = timezone.now()
        self.plan.save()
        scheduling.audit(self.plan, self.admin, "发布计划")
        self.assertContains(self.client.post(self.url, {"token": token}), "仅可删除从未发布的草稿计划")
        self.plan.published_at = None
        self.plan.save()
        scheduling.audit(self.plan, self.admin, "撤回计划发布")
        self.assertContains(self.client.get(self.url), "已有发布或其他受保护的历史记录")
        self.assertContains(self.client.get(self.detail), "已有发布或其他受保护的历史记录")

    def test_task_assignment_after_preview_blocks_delete(self):
        token = self.client.get(self.url).context["token"]
        self.task.executions.create(user=self.member)
        self.assertContains(self.client.post(self.url, {"token": token}), "计划已有任务分配")
        self.assertTrue(self.task.executions.filter(user=self.member).exists())
