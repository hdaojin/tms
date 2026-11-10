from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.navigation import get_section_items

from .models import TrainingChangeRecord, TrainingLog, TrainingPlan, TrainingScheduleDay, TrainingScheduleSlot
from .selectors import training_log_submission_statistics
from .tests import TrainingFixtureMixin, User


class TrainingLogStatisticsTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.first = self.today - timedelta(days=4)
        self.second = self.first + timedelta(days=1)
        self.third = self.second + timedelta(days=1)
        self.user = User.objects.create_user("viewer", last_name="张", first_name="三")
        self.coach = User.objects.create_user("coach", last_name="李", first_name="四", is_active=False)
        self.student = User.objects.create_user("student", last_name="王", first_name="五")
        self.cycle_obj = self.cycle(start_date=self.first, end_date=self.today + timedelta(days=10))
        self.plan = self.make_plan("当前计划")
        for person in (self.user, self.student):
            self.plan.participants.create(user=person, was_initial=True)
        self.snapshot(self.first, [], [self.user, self.student])
        self.day(self.first, self.coach)
        self.day(self.second, self.coach)
        self.day(self.third, kind=TrainingScheduleSlot.Kind.REST)
        self.day(self.today + timedelta(days=1), self.coach)
        self.grant("view_traininglog_statistics")
        self.client.force_login(self.user)
        self.url = reverse("training:monthly_stats")

    def make_plan(self, title, **kwargs):
        defaults = {
            "start_date": self.first, "end_date": self.today + timedelta(days=1),
            "published_at": timezone.now(), "schedule_published_at": timezone.now(),
        }
        return TrainingPlan.objects.create(
            training_cycle=self.cycle_obj, title=title, created_by=self.user, **(defaults | kwargs),
        )

    def snapshot(self, day, before, after):
        when = timezone.make_aware(datetime.combine(day, datetime.min.time()))
        with patch("django.utils.timezone.now", return_value=when):
            TrainingChangeRecord.objects.create(
                training_plan=self.plan, actor=self.user, action="保存名单",
                before={"参与选手": [user.pk for user in before]} if before else {},
                after={"参与选手": [user.pk for user in after]},
            )

    def day(self, date, *coaches, kind=TrainingScheduleSlot.Kind.GENERAL, period=TrainingScheduleSlot.Period.MORNING):
        schedule, _ = TrainingScheduleDay.objects.get_or_create(training_plan=self.plan, date=date)
        slot = schedule.slots.create(period=period, kind=kind)
        slot.coaches.set(coaches)
        return slot

    def grant(self, *codes):
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label="training", codename__in=codes))
        for key in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            self.user.__dict__.pop(key, None)

    def log(self, user, day, **kwargs):
        return TrainingLog.objects.create(training_cycle=self.cycle_obj, author=user, training_date=day, **kwargs)

    def stats(self, **kwargs):
        return training_log_submission_statistics(self.user, plan=self.plan, **kwargs)

    def test_default_current_plan_and_history(self):
        self.grant("view_all_traininglog")
        recent = self.make_plan("最近开始的计划", start_date=self.second)
        history = self.make_plan("历史计划", end_date=self.third)
        self.make_plan("未发布排班", schedule_published_at=None)
        self.make_plan("未来计划", start_date=self.today + timedelta(days=1))
        response = self.client.get(self.url)
        self.assertEqual(response.context["selected_plan"], recent)
        self.assertNotContains(response, "未发布排班")
        self.assertNotContains(response, "未来计划")
        response = self.client.get(self.url, {"plan": history.pk})
        self.assertEqual(response.context["selected_plan"], history)
        self.assertContains(response, "个人日志提交份数")

    def test_personal_scope_and_forged_plan(self):
        self.log(self.user, self.first)
        self.log(self.coach, self.first)
        private = self.make_plan("其他人员的计划")
        response = self.client.get(self.url)
        self.assertContains(response, "张三")
        self.assertNotContains(response, "李四")
        self.assertNotContains(response, "王五")
        self.assertNotContains(response, private.title)
        response = self.client.get(self.url, {"plan": private.pk})
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn("rows", response.context)

    def test_daily_roles_rest_future_and_backfill(self):
        self.grant("view_all_traininglog")
        self.day(self.first, self.coach, period=TrainingScheduleSlot.Period.AFTERNOON)
        TrainingScheduleDay.objects.get(training_plan=self.plan, date=self.first).duty_coaches.add(self.student)
        self.log(self.user, self.first, is_backfill=True)
        self.log(self.coach, self.first)
        self.log(self.student, self.third)
        result = self.stats()
        self.assertEqual([row["date"] for row in result["rows"]], [self.first, self.second])
        first = result["rows"][0]
        self.assertEqual([person["name"] for person in first["submitted_competitors"]], ["张三"])
        self.assertEqual([person["name"] for person in first["submitted_coaches"]], ["李四"])
        self.assertEqual(first["unsubmitted_competitors"], ["王五"])
        self.assertEqual({p["name"]: p["count"] for p in result["people"]}, {"张三": 1, "李四": 1, "王五": 0})

    def test_membership_changes_apply_on_local_date_and_last_change_wins(self):
        self.grant("view_all_traininglog")
        self.snapshot(self.second, [self.user, self.student], [self.student])
        self.snapshot(self.second, [self.student], [self.user, self.student])
        self.snapshot(self.second, [self.user, self.student], [self.student])
        self.plan.participants.filter(user=self.user).update(is_active=False)
        self.log(self.user, self.second)
        first, second = self.stats()["rows"]
        self.assertEqual(first["unsubmitted_competitors"], ["张三", "王五"])
        self.assertEqual(second["unsubmitted_competitors"], ["王五"])
        self.assertEqual(second["submitted_competitors"], [])

    def test_missing_roster_is_reported_without_guessing_absences(self):
        self.grant("view_all_traininglog")
        legacy = self.make_plan("历史缺少名单的计划", end_date=self.second)
        legacy.participants.create(user=self.user, was_initial=True)
        schedule = legacy.schedule_days.create(date=self.first)
        slot = schedule.slots.create(period="morning", kind="general")
        slot.coaches.add(self.coach)
        self.log(self.user, self.first)
        response = self.client.get(self.url, {"plan": legacy.pk})
        self.assertContains(response, "名单不完整，无法核定")
        row = response.context["rows"][0]
        self.assertEqual([p["name"] for p in row["submitted_competitors"]], ["张三"])
        self.assertEqual(row["unsubmitted_competitors"], [])

    def test_same_log_counts_once_per_plan_even_with_both_roles(self):
        self.grant("view_all_traininglog")
        self.day(self.first, self.user, period=TrainingScheduleSlot.Period.AFTERNOON)
        overlap = self.make_plan("重叠计划")
        overlap.participants.create(user=self.user, was_initial=True)
        overlap.schedule_days.create(date=self.first).slots.create(period="morning", kind="general")
        log = self.log(self.user, self.first)
        other_cycle = self.cycle(code="OTHER", start_date=self.first, end_date=self.today)
        TrainingLog.objects.create(training_cycle=other_cycle, author=self.student, training_date=self.first)

        result = self.stats()
        first = result["rows"][0]
        self.assertEqual(first["submitted_competitors"][0]["log_id"], log.pk)
        self.assertEqual(first["submitted_coaches"][0]["log_id"], log.pk)
        self.assertEqual(first["unsubmitted_competitors"], ["王五"])
        self.assertEqual(result["people"][0]["count"], 1)
        self.assertEqual(training_log_submission_statistics(self.user, plan=overlap)["people"][0]["count"], 1)

    def test_filters_share_scope_in_chart_and_daily_table(self):
        self.grant("view_all_traininglog")
        self.log(self.user, self.second)
        response = self.client.get(
            self.url, {"q": "zs", "date_from": self.second.isoformat()}, headers={"HX-Request": "true"},
        )
        self.assertContains(response, "张三")
        self.assertNotContains(response, "王五")
        self.assertNotContains(response, "list-filter-search")
        self.assertEqual([row["date"] for row in response.context["rows"]], [self.second])
        self.assertEqual([p["count"] for p in response.context["people"]], [1])
        for params in (
            {"date_from": "not a date"}, {"date_from": self.second, "date_to": self.first}, {"plan": "invalid"},
        ):
            with self.subTest(params=params):
                response = self.client.get(self.url, params)
                self.assertTrue(response.context["form"].errors)
                self.assertNotIn("rows", response.context)

    def test_permission_navigation_and_detail_links(self):
        detail = reverse("training:log_detail", args=[self.log(self.user, self.first).pk])
        self.assertNotContains(self.client.get(self.url), f'href="{detail}"')
        self.grant("view_traininglog")
        self.assertContains(self.client.get(self.url), f'href="{detail}"')

        def statistics_entries():
            return [
                child for group in get_section_items("training", self.user)
                for child in group.children if child.url_name == "training:monthly_stats"
            ]

        self.assertEqual([entry.resolved_url for entry in statistics_entries()], [self.url])
        self.user.user_permissions.clear()
        self.user = User.objects.get(pk=self.user.pk)
        self.assertEqual(statistics_entries(), [])
        self.assertEqual(self.client.get(self.url).status_code, 403)
