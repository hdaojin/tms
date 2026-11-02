from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TrainingCycleMember, TrainingPlan, TrainingPlanParticipant, TrainingTask, TaskExecution
from .plan_members import confirm_members, preview_members
from .tests import TrainingFixtureMixin, User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PlanMembersTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.cycle_obj = self.cycle()
        self.bind(self.cycle_obj)
        self.cycle_obj.status = "active"
        self.cycle_obj.save()
        self.admin = User.objects.create_superuser("member-admin")
        self.plan = TrainingPlan.objects.create(
            training_cycle=self.cycle_obj, title="成员管理计划", objective="训练", created_by=self.admin,
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
        )
        self.student = self.student_user("student")
        self.url = reverse("training:plan_members", args=[self.plan.pk])
        self.client.force_login(self.admin)

    def student_user(self, name, *, current=True, active=True, role="competitor", cycle=None):
        user = User.objects.create_user(name, is_active=active)
        TrainingCycleMember.objects.create(training_cycle=cycle or self.cycle_obj, user=user, role=role, is_current=current)
        return user

    def preview(self, users=None, operation="add"):
        return preview_members(actor=self.admin, plan=self.plan, ids=[u.pk for u in (users or [self.student])],
                               operation=operation, return_query="mode=add&q=student&page=99")

    def confirm(self, preview):
        return confirm_members(actor=self.admin, plan=self.plan, token=preview["token"])

    def test_candidates_filter_and_bulk_preview_does_not_write(self):
        self.student_user("former", current=False)
        self.student_user("disabled", active=False)
        self.student_user("coach", role="coach")
        other = self.cycle("other")
        self.bind(other)
        other.status = "active"
        other.save()
        self.student_user("outsider", cycle=other)
        response = self.client.get(self.url, {"mode": "add"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context["table"].data.data.values_list("pk", flat=True)), {self.student.pk})
        response = self.client.post(self.url + "?mode=add&q=student", {
            "stage": "select", "operation": "add", "selection": "selected", "users": [self.student.pk],
        })
        self.assertContains(response, "确认添加计划成员")
        self.assertFalse(self.plan.participants.exists())
        token = response.context["token"]
        response = self.client.post(self.url, {"stage": "confirm", "token": token})
        self.assertRedirects(response, self.url + "?mode=add&q=student")
        self.assertTrue(self.plan.participants.filter(user=self.student, is_active=True, was_initial=False).exists())
        self.assertEqual(self.plan.change_records.get().action, "添加计划成员")

    def test_remove_and_restore_keep_identity_and_execution(self):
        participant = TrainingPlanParticipant.objects.create(training_plan=self.plan, user=self.student, was_initial=True)
        task = TrainingTask.objects.create(training_plan=self.plan, title="历史任务", created_by=self.admin,
                                           planned_date=self.plan.start_date)
        execution = TaskExecution.objects.create(training_task=task, user=self.student, status="completed")
        self.plan.published_at = timezone.now()
        self.plan.save()
        remove_url = reverse("training:plan_member_remove", args=[self.plan.pk, participant.pk])
        response = self.client.get(remove_url, {"q": "student"})
        self.assertContains(response, "确认退出计划成员")
        participant.refresh_from_db()
        self.assertTrue(participant.is_active)
        self.client.post(self.url, {"stage": "confirm", "token": response.context["token"]})
        participant.refresh_from_db()
        self.assertFalse(participant.is_active)
        self.confirm(self.preview())
        participant.refresh_from_db()
        self.assertTrue(participant.is_active)
        self.assertTrue(participant.was_initial)
        self.assertEqual(self.plan.participants.get().pk, participant.pk)
        self.assertTrue(TaskExecution.objects.filter(pk=execution.pk).exists())
        newcomer = self.student_user("newcomer")
        self.confirm(self.preview([newcomer]))
        self.assertEqual(task.executions.count(), 1)
        self.assertEqual(self.plan.change_records.count(), 3)

    def test_confirmation_rechecks_eligibility_atomically(self):
        extra = self.student_user("extra")
        preview = self.preview([self.student, extra])
        TrainingCycleMember.objects.filter(user=extra).update(is_current=False)
        with self.assertRaises(ValidationError):
            self.confirm(preview)
        self.assertFalse(self.plan.participants.exists())
        self.assertFalse(self.plan.change_records.exists())

    def test_audit_failure_rolls_back_entire_batch(self):
        extra = self.student_user("extra")
        preview = self.preview([self.student, extra])
        with patch("training.plan_members.audit", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                self.confirm(preview)
        self.assertFalse(self.plan.participants.exists())

    def test_token_actor_plan_tamper_and_replay_protection(self):
        preview = self.preview()
        with self.assertRaises(ValidationError):
            confirm_members(actor=self.admin, plan=self.plan, token=preview["token"] + "bad")
        other_admin = User.objects.create_superuser("other-admin")
        with self.assertRaises(ValidationError):
            confirm_members(actor=other_admin, plan=self.plan, token=preview["token"])
        self.confirm(preview)
        with self.assertRaises(ValidationError):
            self.confirm(preview)

    def test_manager_permissions_and_revocation(self):
        manager = User.objects.create_user("manager")
        manager.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="training", codename__in=["view_trainingplan", "change_trainingplan", "schedule_trainingplan"],
        ))
        self.client.force_login(manager)
        self.assertIn(self.client.get(self.url).status_code, (403, 404))
        self.plan.schedulers.add(manager)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        preview = preview_members(actor=manager, plan=self.plan, ids=[self.student.pk], operation="add")
        manager.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            confirm_members(actor=manager, plan=self.plan, token=preview["token"])
        self.assertFalse(self.plan.participants.exists())

    def test_bulk_selection_must_belong_to_filtered_page(self):
        response = self.client.post(self.url + "?mode=add&q=no-match", {
            "stage": "select", "operation": "add", "selection": "selected", "users": [self.student.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.plan.participants.exists())

    def test_detail_entry_and_list_partial_and_exited_filter(self):
        participant = TrainingPlanParticipant.objects.create(training_plan=self.plan, user=self.student)
        response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
        self.assertContains(response, self.url)
        self.assertEqual(response.context["members_page"].paginator.count, 1)
        participant.is_active = False
        participant.save()
        response = self.client.get(self.url, {"participation": "0"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "student")
        self.assertNotContains(response, "<!DOCTYPE")
        self.assertNotContains(response, "data-row-selection")
        response = self.client.get(self.url + "?mode=add&page=99")
        self.assertEqual(response.context["table"].page.number, 1)

    def test_ineligible_history_can_still_exit_but_cannot_restore(self):
        TrainingPlanParticipant.objects.create(training_plan=self.plan, user=self.student)
        User.objects.filter(pk=self.student.pk).update(is_active=False)
        self.confirm(self.preview(operation="remove"))
        with self.assertRaises(ValidationError):
            self.preview()
