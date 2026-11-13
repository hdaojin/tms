from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TrainingCycleMember, TrainingPlan, TrainingPlanParticipant, TrainingTask, TaskExecution
from .plan_members import change_coaches, change_duty, confirm_members, ordered_duty, preview_members
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
        user = User.objects.create_user(name, first_name=name, is_active=active)
        TrainingCycleMember.objects.create(training_cycle=cycle or self.cycle_obj, user=user, role=role, is_current=current)
        return user

    def preview(self, users=None, operation="add"):
        return preview_members(actor=self.admin, plan=self.plan, ids=[u.pk for u in (users or [self.student])],
                               operation=operation, return_query="mode=add&q=student&page=99")

    def confirm(self, preview):
        return confirm_members(actor=self.admin, plan=self.plan, token=preview["token"])

    def test_rosters_are_edited_independently_on_members_page(self):
        coach = self.student_user("coach", role="coach")
        page = self.client.get(self.url)
        self.assertContains(page, "添加教练")
        self.assertContains(page, "添加值班人员")
        self.assertContains(page, "参与选手")
        response = self.client.post(reverse("training:plan_staff_action", args=[self.plan.pk, "responsible_coaches"]), {
            "operation": "add", "users": [coach.pk],
        })
        self.assertRedirects(response, self.url + "#coaches")
        response = self.client.post(reverse("training:plan_staff_action", args=[self.plan.pk, "duty_personnel"]), {
            "operation": "add", "users": [coach.pk], f"order_{coach.pk}": 1,
        })
        self.assertEqual(response.status_code, 302)
        self.client.post(self.url, {
            "stage": "roster", "roster": "responsible_coaches", "responsible_coaches": [self.student.pk],
        })
        self.assertEqual(list(self.plan.responsible_coaches.all()), [coach])
        self.assertEqual(list(self.plan.duty_personnel.all()), [coach])
        self.assertFalse(self.plan.participants.exists())

    @patch("training.views.timezone.localdate", return_value=date(2026, 1, 2))
    def test_my_plans_shows_only_personal_plans_and_filters_history(self, localdate):
        self.student.user_permissions.add(Permission.objects.get(codename="view_trainingplan"))
        self.plan.end_date = timezone.localdate()
        self.plan.published_at = timezone.now()
        self.plan.save()
        TrainingPlanParticipant.objects.create(training_plan=self.plan, user=self.student)
        history = TrainingPlan.objects.create(
            training_cycle=self.cycle_obj, title="历史计划", created_by=self.admin,
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 1), published_at=timezone.now(),
        )
        TrainingPlanParticipant.objects.create(training_plan=history, user=self.student)
        TrainingPlan.objects.create(
            training_cycle=self.cycle_obj, title="其他计划", created_by=self.admin,
            start_date=timezone.localdate(), end_date=timezone.localdate(), published_at=timezone.now(),
        )
        self.client.force_login(self.student)
        url = reverse("training:my_plans")
        self.assertEqual(list(self.client.get(url).context["object_list"]), [self.plan])
        self.assertEqual(list(self.client.get(url, {"status": "completed"}).context["object_list"]), [history])
        self.client.force_login(self.admin)
        self.assertEqual(list(self.client.get(url).context["object_list"]), [])

    def test_candidates_filter_and_direct_add(self):
        former = self.student_user("former", current=False)
        self.student_user("disabled", active=False)
        self.student_user("coach", role="coach")
        other = self.cycle("other")
        self.bind(other)
        other.status = "active"
        other.save()
        self.student_user("outsider", cycle=other)
        response = self.client.get(self.url, {"mode": "add"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context["table"].data.data.values_list("pk", flat=True)), {self.student.pk, former.pk})
        response = self.client.post(self.url + "?mode=add&q=student", {
            "stage": "select", "operation": "add", "selection": "selected", "users": [self.student.pk],
        })
        self.assertRedirects(response, self.url + "#participants")
        self.assertTrue(self.plan.participants.filter(user=self.student, is_active=True, was_initial=False).exists())
        self.assertEqual(self.plan.change_records.get().action, "添加计划成员")

    def test_group_add_freezes_eligible_members_at_preview(self):
        group = Group.objects.create(name="第一梯队")
        disabled = self.student_user("disabled", active=False)
        group.user_set.add(self.student, disabled)
        individual = self.student_user("individual")
        url = self.url + "?mode=add"
        response = self.client.post(url, {
            "stage": "select", "operation": "add", "selection": "selected",
            "group_selection": "1", "groups": [group.pk], "users": [individual.pk],
        })
        self.assertContains(response, "将添加 2 位选手")
        self.assertFalse(self.plan.participants.exists())
        newcomer = self.student_user("newcomer")
        group.user_set.add(newcomer)
        self.assertRedirects(self.client.post(url, {
            "stage": "confirm_groups", "token": response.context["preview"]["token"],
        }), self.url + "#participants")
        self.assertSetEqual(set(self.plan.participants.values_list("user_id", flat=True)), {
            self.student.pk, individual.pk,
        })
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.implementation_audience, group.name)

    def test_remove_and_restore_keep_identity_and_execution(self):
        participant = TrainingPlanParticipant.objects.create(training_plan=self.plan, user=self.student, was_initial=True)
        task = TrainingTask.objects.create(training_plan=self.plan, title="历史任务", created_by=self.admin,
                                           planned_date=self.plan.start_date, status="published")
        execution = TaskExecution.objects.create(training_task=task, user=self.student, status="completed")
        self.plan.published_at = timezone.now()
        self.plan.save()
        TrainingPlanParticipant.objects.create(training_plan=self.plan, user=self.student_user("remaining"))
        remove_url = reverse("training:plan_member_remove", args=[self.plan.pk, participant.pk])
        response = self.client.get(self.url, {"q": "student"})
        self.assertContains(response, "确认退出")
        self.assertContains(response, "remove-member-")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        participant.refresh_from_db()
        self.assertTrue(participant.is_active)
        self.client.post(remove_url + "?q=student")
        participant.refresh_from_db()
        self.assertFalse(participant.is_active)
        self.confirm(self.preview())
        participant.refresh_from_db()
        self.assertTrue(participant.is_active)
        self.assertTrue(participant.was_initial)
        self.assertEqual(self.plan.participants.get(user=self.student).pk, participant.pk)
        self.assertTrue(TaskExecution.objects.filter(pk=execution.pk).exists())
        newcomer = self.student_user("newcomer")
        self.confirm(self.preview([newcomer]))
        self.assertEqual(task.executions.count(), 1)
        self.assertEqual(self.plan.change_records.count(), 3)

    def test_confirmation_rechecks_eligibility_atomically(self):
        extra = self.student_user("extra")
        preview = self.preview([self.student, extra])
        User.objects.filter(pk=extra.pk).update(is_active=False)
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

    def test_coach_candidates_add_and_remove_are_rechecked(self):
        coach = self.student_user("coach", role="coach")
        disabled = self.student_user("disabled-coach", role="coach", active=False)
        response = self.client.get(self.url)
        self.assertEqual({item["user"].pk for item in response.context["coach_section"]["candidates"]}, {coach.pk})
        url = reverse("training:plan_staff_action", args=[self.plan.pk, "responsible_coaches"])
        data = {"operation": "add", "users": [disabled.pk]}
        self.client.post(url, data)
        self.assertFalse(self.plan.responsible_coaches.exists())
        data["users"] = [coach.pk]
        self.client.post(url, data)
        self.assertTrue(self.plan.responsible_coaches.filter(pk=coach.pk).exists())
        page = self.client.get(self.url)
        self.assertContains(page, "确认移除")
        self.client.post(self.url, {"stage": "remove_coach", "user": coach.pk})
        self.assertFalse(self.plan.responsible_coaches.exists())
        self.assertEqual(self.plan.change_records.count(), 2)

    def test_coach_changes_recheck_state_and_published_minimum(self):
        coach = self.student_user("coach", role="coach")
        other = self.student_user("other-coach", role="coach")
        User.objects.filter(pk=other.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            change_coaches(actor=self.admin, plan=self.plan, ids=[coach.pk, other.pk], operation="add")
        self.assertFalse(self.plan.responsible_coaches.exists())
        change_coaches(actor=self.admin, plan=self.plan, ids=[coach.pk], operation="add")
        self.plan.published_at = timezone.now()
        self.plan.save()
        with self.assertRaises(ValidationError):
            change_coaches(actor=self.admin, plan=self.plan, ids=[coach.pk], operation="remove")
        self.assertTrue(self.plan.responsible_coaches.filter(pk=coach.pk).exists())

    def test_duty_order_requires_cycle_coaches_and_preserves_sequence(self):
        coach = self.student_user("duty-one", role="coach")
        other = self.student_user("duty-two", role="coach")
        with self.assertRaises(ValidationError):
            change_duty(actor=self.admin, plan=self.plan, operation="add", orders={self.student.pk: 1})
        change_duty(actor=self.admin, plan=self.plan, operation="add", orders={coach.pk: 9, other.pk: 3})
        self.assertEqual(list(ordered_duty(self.plan).values_list("pk", flat=True)), [other.pk, coach.pk])
        change_duty(actor=self.admin, plan=self.plan, operation="order", orders={coach.pk: 1, other.pk: 2})
        self.assertEqual(list(ordered_duty(self.plan).values_list("pk", flat=True)), [coach.pk, other.pk])

    def test_staff_sections_add_and_remove_in_place(self):
        coach = self.student_user("private-coach", role="coach")
        coach.last_name, coach.first_name = "张", "三"
        coach.save()
        page = self.client.get(self.url)
        self.assertContains(page, "添加值班人员")
        self.assertNotContains(page, "private-coach")
        url = reverse("training:plan_staff_action", args=[self.plan.pk, "duty_personnel"])
        response = self.client.post(url, {"operation": "add", "users": [coach.pk], f"order_{coach.pk}": 8},
                                    HTTP_HX_REQUEST="true")
        self.assertContains(response, "张三")
        self.assertNotContains(response, "<!DOCTYPE")
        self.assertEqual(ordered_duty(self.plan).get(pk=coach.pk).duty_order, 8)
        response = self.client.post(url, {"operation": "remove", "user": coach.pk}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.plan.duty_personnel.exists())

    def test_duplicate_coaches_require_distinct_notes(self):
        from accounts.models import UserProfile

        first = self.student_user("coach-one", role="coach")
        second = self.student_user("coach-two", role="coach")
        User.objects.filter(pk__in=[first.pk, second.pk]).update(last_name="张", first_name="三")
        page = self.client.get(self.url)
        self.assertContains(page, "重名备注未填写或重复")
        url = reverse("training:plan_staff_action", args=[self.plan.pk, "responsible_coaches"])
        self.client.post(url, {"operation": "add", "users": [first.pk]})
        self.assertFalse(self.plan.responsible_coaches.exists())
        UserProfile.objects.create(user=first, name_disambiguation="一组")
        UserProfile.objects.create(user=second, name_disambiguation="二组")
        page = self.client.get(self.url)
        self.assertContains(page, "张三（一组）")
        self.client.post(url, {"operation": "add", "users": [first.pk]})
        self.assertTrue(self.plan.responsible_coaches.filter(pk=first.pk).exists())

    def test_participant_htmx_add_returns_existing_section(self):
        response = self.client.get(self.url, {"mode": "add", "section": "participants"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "预览添加名单")
        self.assertNotContains(response, "<!DOCTYPE")
        response = self.client.post(self.url + "?mode=add", {
            "stage": "select", "operation": "add", "selection": "selected", "users": [self.student.pk],
        }, HTTP_HX_REQUEST="true")
        self.assertContains(response, "已添加计划成员")
        self.assertContains(response, "退出计划")
        self.assertNotContains(response, "预览添加名单")
        self.assertEqual(response.headers["HX-Push-Url"], self.url)

    def test_participant_table_shows_birth_date_and_age(self):
        from accounts.models import UserProfile

        UserProfile.objects.create(user=self.student, birth_date=date(2008, 3, 4))
        TrainingPlanParticipant.objects.create(training_plan=self.plan, user=self.student)
        with patch("training.member_tables.timezone.localdate", return_value=date(2026, 3, 3)):
            response = self.client.get(self.url)
        self.assertContains(response, "出生日期")
        self.assertContains(response, "2008-03-04")
        self.assertContains(response, ">17<", html=False)

    def test_coach_selector_rejects_ineligible_users(self):
        self.student_user("coach", role="coach")
        response = self.client.get(self.url)
        self.assertContains(response, 'data-staff-search')
        self.client.post(reverse("training:plan_staff_action", args=[self.plan.pk, "responsible_coaches"]), {
            "operation": "add", "users": [self.student.pk],
        }, HTTP_HX_REQUEST="true")
        self.assertFalse(self.plan.responsible_coaches.exists())

    def test_detail_entry_and_list_partial_and_exited_filter(self):
        participant = TrainingPlanParticipant.objects.create(training_plan=self.plan, user=self.student)
        response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
        self.assertContains(response, self.url)
        self.assertEqual(dict(response.context["participant_groups"])["参与选手"], [self.student])
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
