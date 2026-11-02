from datetime import date

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import TrainingPlan, TrainingCycleMember
from .plan_people import PlanStaffSelect
from .tests import TrainingFixtureMixin, User, configure_test_periods


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PlanPeopleTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        configure_test_periods()
        self.admin = User.objects.create_superuser("people-manager", password="test")
        self.people = [User.objects.create_user(f"staff-candidate-{number:02d}") for number in range(23)]
        permissions = Permission.objects.filter(content_type__app_label="training", codename__in=["schedule_trainingplan", "approve_trainingplan"])
        for person in self.people:
            person.user_permissions.add(*permissions)
        self.period = self.cycle()
        TrainingCycleMember.objects.create(training_cycle=self.period, user=self.people[-1], role="competitor")
        self.plan = TrainingPlan.objects.create(
            training_cycle=self.period,
            title="人员搜索计划",
            objective="训练",
            created_by=self.admin,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )
        self.client.force_login(self.admin)
        self.search_url = reverse("training:plan_staff_search")

    def test_create_renders_two_search_pickers_without_enumerating_candidates(self):
        response = self.client.get(reverse("training:plan_create"))
        self.assertContains(response, "data-plan-people", count=2)
        self.assertContains(response, "js/training-plan-people.js")
        self.assertNotContains(response, "staff-candidate-00")
        for name in ("schedulers", "approvers"):
            self.assertIsInstance(response.context["form"].fields[name].widget, PlanStaffSelect)
        self.assertNotIn("task_managers", response.context["form"].fields)
        self.assertNotIn("competitors", response.context["form"].fields)

    def test_edit_renders_only_saved_selections_and_object_scoped_search_url(self):
        self.plan.schedulers.add(self.people[0])
        self.plan.approvers.add(self.people[1])
        self.plan.task_managers.add(self.people[2])
        response = self.client.get(reverse("training:plan_edit", args=[self.plan.pk]))
        for index, name in enumerate(("schedulers", "approvers")):
            widget = response.context["form"].fields[name].widget
            self.assertEqual([person["id"] for person in widget.selected], [self.people[index].pk])
            self.assertEqual(widget.plan_id, self.plan.pk)
        self.assertNotContains(response, "staff-candidate-03")
        self.assertContains(response, f"{self.search_url}?plan={self.plan.pk}")

    def test_invalid_submission_preserves_each_selected_list(self):
        response = self.client.post(
            reverse("training:plan_create"),
            {
                "training_cycle": self.period.pk,
                "competitors": [self.people[-1].pk],
                "title": "",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "objective": "训练",
                **{f"{p}_{edge}": value for p, a, b in [("early", "08:00", "09:00"), ("morning", "09:00", "12:00"), ("afternoon", "14:00", "17:00"), ("evening", "19:00", "21:00")] for edge, value in [("start", a), ("end", b)]},
                "status": "draft",
                "schedulers": [self.people[0].pk],
                "approvers": [self.people[1].pk],
                "task_managers": [self.people[2].pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        for index, name in enumerate(("schedulers", "approvers")):
            self.assertEqual(response.context["form"].fields[name].widget.selected[0]["id"], self.people[index].pk)

    def test_search_requires_input_and_paginates(self):
        self.assertEqual(self.client.get(self.search_url, {"role": "schedulers"}).json(), {"results": [], "has_more": False})
        first = self.client.get(self.search_url, {"q": "staff-candidate", "role": "schedulers"})
        self.assertEqual(len(first.json()["results"]), 20)
        self.assertTrue(first.json()["has_more"])
        self.assertEqual(first.headers["Cache-Control"], "private, no-store")
        second = self.client.get(self.search_url, {"q": "staff-candidate", "page": 2, "role": "schedulers"}).json()
        self.assertEqual(len(second["results"]), 3)
        self.assertFalse(second["has_more"])

    def test_search_picker_submission_saves_all_three_person_lists(self):
        response = self.client.post(
            reverse("training:plan_create"),
            {
                "training_cycle": self.period.pk,
                "competitors": [self.people[-1].pk],
                "title": "搜索人员后保存",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "objective": "训练",
                **{f"{p}_{edge}": value for p, a, b in [("early", "08:00", "09:00"), ("morning", "09:00", "12:00"), ("afternoon", "14:00", "17:00"), ("evening", "19:00", "21:00")] for edge, value in [("start", a), ("end", b)]},
                "status": "draft",
                "schedulers": [self.people[0].pk, self.people[1].pk],
                "approvers": [self.people[2].pk],
                "task_managers": [self.people[3].pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        plan = TrainingPlan.objects.get(title="搜索人员后保存")
        self.assertSetEqual(set(plan.schedulers.values_list("pk", flat=True)), {self.people[0].pk, self.people[1].pk})
        self.assertEqual(list(plan.approvers.values_list("pk", flat=True)), [self.people[2].pk])
        self.assertFalse(plan.task_managers.exists())

    def test_search_supports_full_chinese_name(self):
        person = self.people[0]
        person.last_name, person.first_name = "张", "三"
        person.save()
        result = self.client.get(self.search_url, {"q": "张三", "role": "schedulers"}).json()["results"]
        self.assertEqual([row["id"] for row in result], [person.pk])

    def test_search_checks_create_permission_and_plan_management_scope(self):
        viewer = self.people[0]
        viewer.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="training",
                codename__in=["view_trainingplan", "change_trainingplan"],
            )
        )
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.search_url, {"q": "staff"}).status_code, 403)
        self.assertIn(self.client.get(self.search_url, {"plan": self.plan.pk, "q": "staff"}).status_code, [403, 404])
        self.plan.schedulers.add(viewer)
        self.assertEqual(self.client.get(self.search_url, {"plan": self.plan.pk, "q": "staff", "role": "schedulers"}).status_code, 200)

    def test_invalid_paging_and_plan_identifier_return_validation_error(self):
        for params in ({"page": 0}, {"page": "bad"}, {"q": "x" * 101}, {"plan": "bad"}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(self.search_url, params).status_code, 400)

    def edit_data(self, **extra):
        from .forms import TrainingPlanForm
        form = TrainingPlanForm(instance=self.plan)
        data = {"action": "save"}
        for name in ("training_cycle", "title", "start_date", "end_date", "objective", *TrainingPlan.TIME_FIELDS):
            value = form[name].value()
            if value is not None:
                data[name] = value.isoformat() if hasattr(value, "isoformat") else value
        # 未初始化的测试计划也要填写作息。
        data.update({"morning_start": "09:00", "morning_end": "12:00", "afternoon_start": "14:00", "afternoon_end": "17:00"})
        return data | extra

    def test_empty_edit_defaults_all_but_only_save_applies_snapshot(self):
        from .forms import TrainingPlanForm
        self.assertTrue(TrainingPlanForm(instance=self.plan)["all_competitors"].value())
        self.assertFalse(self.plan.participants.exists())
        response = self.client.post(reverse("training:plan_edit", args=[self.plan.pk]), self.edit_data(all_competitors="on"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(self.plan.participants.filter(is_active=True).values_list("user_id", flat=True)), {self.people[-1].pk})
        newcomer = User.objects.create_user("late-plan-student")
        TrainingCycleMember.objects.create(training_cycle=self.period, user=newcomer, role="competitor")
        self.assertFalse(self.plan.participants.filter(user=newcomer).exists())
        self.assertFalse(TrainingPlanForm(instance=self.plan)["all_competitors"].value())
        self.client.post(reverse("training:plan_edit", args=[self.plan.pk]), self.edit_data(all_competitors="on"))
        self.assertTrue(self.plan.participants.filter(user=newcomer, is_active=True).exists())
        self.assertFalse(self.plan.participants.filter(was_initial=True).exists())

    def test_group_and_individual_selection_is_cycle_intersection_and_union(self):
        from django.contrib.auth.models import Group
        extra = User.objects.create_user("second-team-student")
        TrainingCycleMember.objects.create(training_cycle=self.period, user=extra, role="competitor")
        first = Group.objects.create(name="第一梯队")
        second = Group.objects.create(name="第二梯队")
        first.user_set.add(self.people[-1], self.people[0])
        second.user_set.add(extra, self.people[-1])
        url = reverse("training:plan_edit", args=[self.plan.pk])
        response = self.client.post(url, self.edit_data(competitor_groups=[first.pk, second.pk], competitors=[extra.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(self.plan.participants.filter(is_active=True).values_list("user_id", flat=True)), {extra.pk, self.people[-1].pk})
        first.user_set.clear()
        self.assertEqual(self.plan.participants.filter(is_active=True).count(), 2)
        response = self.client.post(url, self.edit_data(competitors=[self.people[0].pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("competitors", response.context["form"].errors)
        unrelated = Group.objects.create(name="无关组")
        response = self.client.post(url, self.edit_data(competitor_groups=[unrelated.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("competitor_groups", response.context["form"].errors)

    def test_competitor_search_ignores_forged_cycle_for_existing_plan(self):
        other = self.cycle("OTHER-SEARCH")
        TrainingCycleMember.objects.create(training_cycle=other, user=self.people[0], role="competitor")
        response = self.client.get(self.search_url, {"plan": self.plan.pk, "cycle": other.pk, "role": "competitor", "q": "staff-candidate"})
        self.assertEqual([row["id"] for row in response.json()["results"]], [self.people[-1].pk])
