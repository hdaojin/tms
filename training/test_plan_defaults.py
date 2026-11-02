from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import TrainingCycle, TrainingCycleMember, TrainingPlan
from .tests import TrainingFixtureMixin, User, configure_test_periods


class TrainingPlanDefaultCycleTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        configure_test_periods()
        self.user = User.objects.create_superuser("plan_manager", password="test")
        self.current_cycle = self.cycle("CURRENT")
        self.bind(self.current_cycle)
        self.current_cycle.status = TrainingCycle.Status.ACTIVE
        self.current_cycle.save()
        self.other_cycle = self.cycle("OTHER")
        self.student = User.objects.create_user("plan-student")
        TrainingCycleMember.objects.create(user=self.student, training_cycle=self.other_cycle, role="competitor")
        self.client.force_login(self.user)
        self.create_url = reverse("training:plan_create")

    def set_current_cycle(self):
        TrainingCycleMember.objects.create(
            user=self.user, training_cycle=self.current_cycle, role="coach", is_current=True
        )

    def plan_data(self, **overrides):
        return {
            "training_cycle": self.other_cycle.pk,
            "title": "训练计划",
            "start_date": "2026-01-02",
            "end_date": "2026-01-03",
            "objective": "训练目标",
            **{f"{p}_{edge}": value for p, a, b in [("early", "08:00", "09:00"), ("morning", "09:00", "12:00"), ("afternoon", "14:00", "17:00"), ("evening", "19:00", "21:00")] for edge, value in [("start", a), ("end", b)]},
            "schedulers": [self.user.pk],
            "competitors": [self.student.pk],
            "status": TrainingPlan.Status.DRAFT,
            **overrides,
        }

    def test_create_defaults_to_users_current_cycle_even_if_completed(self):
        self.set_current_cycle()
        TrainingCycle.objects.filter(pk=self.current_cycle.pk).update(status=TrainingCycle.Status.COMPLETED)
        response = self.client.get(self.create_url)
        self.assertEqual(response.context["form"]["training_cycle"].value(), self.current_cycle.pk)

    def test_create_without_current_cycle_has_no_default(self):
        response = self.client.get(self.create_url)
        self.assertIsNone(response.context["form"]["training_cycle"].value())
        self.assertFalse(response.context["form"]["schedulers"].value())
        self.assertNotContains(response, "尚未指定")

    def test_manually_selected_cycle_is_saved(self):
        self.set_current_cycle()
        response = self.client.post(self.create_url, self.plan_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TrainingPlan.objects.get(title="训练计划").training_cycle, self.other_cycle)

    def test_invalid_submission_preserves_selected_cycle(self):
        self.set_current_cycle()
        response = self.client.post(self.create_url, self.plan_data(title=""))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.context["form"]["training_cycle"].value()), str(self.other_cycle.pk))

    def test_edit_preserves_existing_cycle(self):
        self.set_current_cycle()
        data = self.plan_data()
        data["training_cycle"] = self.other_cycle
        data["start_date"] = date(2026, 1, 2)
        data["end_date"] = date(2026, 1, 3)
        data.pop("schedulers")
        data.pop("competitors")
        plan = TrainingPlan.objects.create(created_by=self.user, **data)
        response = self.client.get(reverse("training:plan_edit", args=[plan.pk]))
        self.assertEqual(response.context["form"]["training_cycle"].value(), self.other_cycle.pk)
        self.assertIn('value="2026-01-02"', str(response.context["form"]["start_date"]))
        self.assertIn('value="2026-01-03"', str(response.context["form"]["end_date"]))
        response = self.client.post(reverse("training:plan_edit", args=[plan.pk]), self.plan_data())
        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.start_date, date(2026, 1, 2))
        self.assertEqual(plan.end_date, date(2026, 1, 3))
