from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import TrainingCycle, TrainingPlan
from .tests import TrainingFixtureMixin, User


class TrainingListPageTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.manager = User.objects.create_superuser("training-list-manager", password="test")
        self.client.force_login(self.manager)

    def plan(self, cycle, title, *, end_date=date(2026, 1, 20), published=False, owner=None):
        return TrainingPlan.objects.create(
            training_cycle=cycle, title=title, start_date=date(2026, 1, 1), end_date=end_date,
            published_at=timezone.now() if published else None, created_by=owner or self.manager,
        )

    def table_ids(self, response):
        return {row.record.pk for row in response.context["table"].rows}

    def test_both_pages_use_common_template_filters_and_creation_buttons(self):
        for list_name, create_name in (("cycle_list", "cycle_create"), ("plan_list", "plan_create")):
            with self.subTest(page=list_name):
                response = self.client.get(reverse(f"training:{list_name}"))
                self.assertTemplateUsed(response, "common/table_page.html")
                self.assertTemplateUsed(response, "components/list_filter_toolbar.html")
                self.assertContains(response, 'name="q"')
                self.assertContains(response, 'name="status"')
                self.assertContains(response, reverse(f"training:{create_name}"))

    def test_creation_buttons_respect_permissions(self):
        viewer = User.objects.create_user("training-list-viewer")
        viewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="training", codename__in=("view_trainingcycle", "view_trainingplan")
        ))
        self.client.force_login(viewer)
        for list_name, create_name in (("cycle_list", "cycle_create"), ("plan_list", "plan_create")):
            response = self.client.get(reverse(f"training:{list_name}"))
            self.assertNotContains(response, reverse(f"training:{create_name}"))
            self.assertEqual(self.client.get(reverse(f"training:{create_name}")).status_code, 403)

        viewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="training", codename__in=("add_trainingcycle", "add_trainingplan")
        ))
        self.client.force_login(User.objects.get(pk=viewer.pk))
        for list_name, create_name in (("cycle_list", "cycle_create"), ("plan_list", "plan_create")):
            self.assertContains(self.client.get(reverse(f"training:{list_name}")), reverse(f"training:{create_name}"))

    def test_cycle_search_and_status_filter_can_be_combined(self):
        active = self.cycle("ACTIVE", name="Linux 集训")
        self.bind(active)
        active.status = TrainingCycle.Status.ACTIVE
        active.save()
        self.cycle("PLANNING", name="Linux 筹备")
        unrelated = self.cycle("OTHER", name="其他周期")
        self.bind(unrelated)
        unrelated.status = TrainingCycle.Status.ACTIVE
        unrelated.save()

        response = self.client.get(reverse("training:cycle_list"), {"q": "Linux", "status": "active"})
        self.assertEqual(self.table_ids(response), {active.pk})
        self.assertContains(response, 'value="active" selected')
        response = self.client.get(reverse("training:cycle_list"), {"q": self.project.name})
        self.assertEqual(self.table_ids(response), {active.pk, unrelated.pk, TrainingCycle.objects.get(code="PLANNING").pk})

    def test_plan_status_filter_matches_displayed_status_at_date_boundary(self):
        cycle = self.cycle()
        past_draft = self.plan(cycle, "过期未发布", end_date=date(2026, 1, 9))
        past_published = self.plan(cycle, "过期已发布", end_date=date(2026, 1, 9), published=True)
        today_draft = self.plan(cycle, "当天未发布", end_date=date(2026, 1, 10))
        today_published = self.plan(cycle, "当天已发布", end_date=date(2026, 1, 10), published=True)
        future_published = self.plan(cycle, "未来已发布", published=True)
        url = reverse("training:plan_list")
        with patch("django.utils.timezone.localdate", return_value=date(2026, 1, 10)):
            for status, expected in (
                ("completed", {past_draft.pk, past_published.pk}),
                ("unpublished", {today_draft.pk}),
                ("published", {today_published.pk, future_published.pk}),
            ):
                with self.subTest(status=status):
                    response = self.client.get(url, {"status": status})
                    self.assertEqual(self.table_ids(response), expected)
            response = self.client.get(url, {"status": "published", "q": "当天"})
            self.assertEqual(self.table_ids(response), {today_published.pk})

    def test_plan_search_never_expands_visible_range(self):
        cycle = self.cycle("SCOPE", name="范围周期")
        viewer = User.objects.create_user("scoped-plan-viewer")
        viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label="training", codename="view_trainingplan"
        ))
        visible = self.plan(cycle, "可见计划", owner=viewer)
        hidden = self.plan(cycle, "不可见计划")
        self.client.force_login(viewer)
        url = reverse("training:plan_list")
        self.assertEqual(self.table_ids(self.client.get(url, {"q": "SCOPE"})), {visible.pk})
        self.assertEqual(self.table_ids(self.client.get(url, {"q": hidden.title})), set())

    def test_plan_edit_action_matches_object_permission(self):
        cycle = self.cycle()
        viewer = User.objects.create_user("plan-edit-scope-viewer")
        viewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="training", codename__in=("view_trainingplan", "change_trainingplan", "schedule_trainingplan")
        ))
        own = self.plan(cycle, "本人计划", owner=viewer)
        assigned = self.plan(cycle, "仅参与排班的计划")
        assigned.schedulers.add(viewer)
        self.client.force_login(viewer)
        list_url = reverse("training:plan_list")
        own_url = reverse("training:plan_edit", args=[own.pk])
        assigned_url = reverse("training:plan_edit", args=[assigned.pk])
        response = self.client.get(list_url)
        self.assertContains(response, own_url)
        self.assertContains(response, assigned_url)
        self.assertEqual(self.client.get(assigned_url).status_code, 200)
        assigned.schedulers.remove(viewer)
        assigned.task_managers.add(viewer)
        self.assertNotContains(self.client.get(list_url), assigned_url)
        self.assertEqual(self.client.get(assigned_url).status_code, 404)

    def test_htmx_filters_return_only_updated_results(self):
        cycle = self.cycle("FRAGMENT", name="局部刷新周期")
        plan = self.plan(cycle, "局部刷新计划")
        for list_name, query, expected in (
            ("cycle_list", {"q": "FRAGMENT", "status": "planning"}, cycle.pk),
            ("plan_list", {"q": "局部刷新计划"}, plan.pk),
        ):
            with self.subTest(page=list_name):
                response = self.client.get(reverse(f"training:{list_name}"), query, HTTP_HX_REQUEST="true")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.table_ids(response), {expected})
                self.assertContains(response, "<table")
                self.assertNotContains(response, "<!doctype html>")
                self.assertNotContains(response, 'class="list-filter-search')

    def test_pagination_preserves_cycle_filters(self):
        TrainingCycle.objects.bulk_create([
            TrainingCycle(skill_project=self.project, code=f"GROUP{number:02}", name=f"周期 {number}",
                          start_date=date(2026, 1, 1))
            for number in range(26)
        ])
        response = self.client.get(reverse("training:cycle_list"), {"q": "GROUP", "status": "planning", "page": "2"})
        self.assertEqual(len(response.context["table"].page.object_list), 1)
        self.assertContains(response, "q=GROUP&amp;status=planning&amp;page=1")
