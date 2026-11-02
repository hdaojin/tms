from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import entry_operations, plan_clear, scheduling
from .test_process_refactor import ProcessFixture


class PlanClearTests(ProcessFixture, TestCase):
    def test_whole_plan_workflow_preserves_history_and_times(self):
        task = self.task(title="已清空的特定任务")
        slot = self.slot
        starts_at = slot.starts_at
        with self.assertRaisesMessage(ValidationError, "先撤回全部任务"):
            entry_operations.withdrawal_state(self.plan, self.admin, "schedule")
        state = plan_clear.state(self.plan, self.admin, "withdraw_tasks")
        plan_clear.execute(self.plan, self.admin, "withdraw_tasks", "调整", state["digest"])
        task.refresh_from_db()
        self.assertEqual(task.status, "draft")
        state = plan_clear.state(self.plan, self.admin, "clear_tasks")
        plan_clear.execute(self.plan, self.admin, "clear_tasks", "调整", state["digest"])
        task.refresh_from_db()
        self.assertEqual(task.status, "cancelled")
        self.client.force_login(self.admin)
        page = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
        visible = [item.pk for day in page.context["entry_days"] for entry in day.slots.all() for item in entry.visible_tasks]
        self.assertNotIn(task.pk, visible)
        self.assertTrue(task.executions.filter(revoked_at__isnull=False).exists())
        old_domains = list(task.domain_links.values_list("technical_domain_id", flat=True))
        old_coaches = list(task.coach_links.values_list("user_id", flat=True))
        self.plan.schedule_published_at = None
        self.plan.save(update_fields=["schedule_published_at", "updated_at"])
        state = plan_clear.state(self.plan, self.admin, "clear_schedule")
        plan_clear.execute(self.plan, self.admin, "clear_schedule", "调整", state["digest"])
        slot.refresh_from_db()
        self.assertEqual(slot.kind, "pending")
        self.assertEqual(slot.starts_at, starts_at)
        self.assertFalse(slot.domains.exists())
        self.assertFalse(slot.coaches.exists())
        self.assertFalse(slot.day.duty_coaches.exists())
        self.assertTrue(task.change_records.exists())
        before = scheduling.slot_snapshot(slot)
        scheduling.save_schedule(self.plan, self.admin, [{"type": "slot", "id": slot.pk,
            "revision": slot.revision, "before": before, "after": before | {"kind": "rest"}}])
        self.assertEqual(list(task.domain_links.values_list("technical_domain_id", flat=True)), old_domains)
        self.assertEqual(list(task.coach_links.values_list("user_id", flat=True)), old_coaches)

    def test_changed_schedule_rejects_confirmation(self):
        self.task()
        state = plan_clear.state(self.plan, self.admin, "withdraw_tasks")
        self.slot.kind = "general"
        self.slot.save(update_fields=["kind", "updated_at"])
        with self.assertRaisesMessage(ValidationError, "重新预览"):
            plan_clear.execute(self.plan, self.admin, "withdraw_tasks", "调整", state["digest"])

    def test_execution_history_blocks_schedule_clear_even_if_task_was_cancelled(self):
        task = self.task()
        execution = task.executions.first()
        execution.started_at = timezone.now()
        execution.save(update_fields=["started_at", "updated_at"])
        task.status = "cancelled"
        task.save(update_fields=["status", "updated_at"])
        self.plan.schedule_published_at = None
        self.plan.save(update_fields=["schedule_published_at", "updated_at"])
        with self.assertRaisesMessage(ValidationError, "执行或进度"):
            plan_clear.state(self.plan, self.admin, "clear_schedule")

    def test_permissions_execution_facts_and_stale_preview(self):
        task = self.task()
        with self.assertRaises(PermissionDenied):
            plan_clear.state(self.plan, self.coach, "withdraw_tasks")
        state = plan_clear.state(self.plan, self.admin, "withdraw_tasks")
        execution = task.executions.first()
        execution.started_at = timezone.now()
        execution.save(update_fields=["started_at", "updated_at"])
        with self.assertRaises(ValidationError):
            plan_clear.execute(self.plan, self.admin, "withdraw_tasks", "调整", state["digest"])
        task.refresh_from_db()
        self.assertEqual(task.status, "published")

    def test_page_previews_and_confirms(self):
        task = self.task()
        self.client.force_login(self.admin)
        url = reverse("training:plan_clear", args=[self.plan.pk, "withdraw_tasks"])
        response = self.client.post(url, {"reason": "调整"})
        self.assertContains(response, task.title)
        response = self.client.post(url, {"token": response.context["token"]})
        self.assertRedirects(response, reverse("training:plan_detail", args=[self.plan.pk]))
        task.refresh_from_db()
        self.assertEqual(task.status, "draft")
