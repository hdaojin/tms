from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.navigation import get_section_items

from .historical_rosters import CONFIRMED, REVOKED
from .log_exemptions import ACTIONS, exemption_history
from .models import (
    TrainingChangeRecord, TrainingCycleMember, TrainingLog, TrainingPlan, TrainingScheduleDay, TrainingScheduleSlot,
    TrainingTask,
)
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
        self.assertEqual(first["unsubmitted_coaches"], [])
        self.assertEqual(result["rows"][1]["unsubmitted_coaches"], ["李四"])
        self.assertEqual({p["name"]: p["expected"] for p in result["people"]}, {"张三": 2, "李四": 2, "王五": 2})
        self.assertEqual({p["name"]: p["count"] for p in result["people"]}, {"张三": 1, "李四": 1, "王五": 0})

    def test_early_reading_does_not_add_days_or_coaches(self):
        self.grant("view_all_traininglog")
        early_coach = User.objects.create_user("early-coach", first_name="早读教练")
        self.day(self.first, early_coach, period=TrainingScheduleSlot.Period.EARLY)
        self.day(self.third, early_coach, period=TrainingScheduleSlot.Period.EARLY)
        self.log(self.user, self.first)
        self.log(self.user, self.third)
        self.log(early_coach, self.first)
        result = self.stats()
        self.assertEqual([row["date"] for row in result["rows"]], [self.first, self.second])
        self.assertEqual(result["rows"][0]["submitted_coaches"], [])
        self.assertEqual(result["rows"][0]["unsubmitted_coaches"], ["李四"])
        self.assertEqual({p["name"]: p["count"] for p in result["people"]}, {"张三": 1, "李四": 0, "王五": 0})

    def test_all_coaches_count_as_submitted_but_only_named_coaches_are_required(self):
        self.grant("view_all_traininglog")
        optional = User.objects.create_user("optional-coach", first_name="其他教练")
        optional.user_permissions.set(
            Permission.objects.filter(content_type__app_label="training", codename="view_traininglog_statistics")
        )
        for date in (self.first, self.second):
            slot = self.plan.schedule_days.get(date=date).slots.get()
            slot.coaches_all = True
            slot.save(update_fields=["coaches_all"])
            slot.coaches.add(optional)
        self.day(self.second, self.coach, period=TrainingScheduleSlot.Period.AFTERNOON)
        first_log = self.log(optional, self.first)
        second_log = self.log(optional, self.second)
        self.log(self.user, self.first)

        result = self.stats()
        first, second = result["rows"]
        self.assertEqual(first["unsubmitted_coaches"], [])
        self.assertEqual(first["unsubmitted_competitors"], ["王五"])
        self.assertEqual(second["unsubmitted_coaches"], ["李四"])
        self.assertEqual(second["unsubmitted_competitors"], ["张三", "王五"])
        self.assertEqual([p["log_id"] for p in first["submitted_coaches"]], [first_log.pk])
        self.assertEqual([p["log_id"] for p in second["submitted_coaches"]], [second_log.pk])
        self.assertEqual(
            {p["user_id"]: (p["count"], p["expected"]) for p in result["people"]},
            {self.user.pk: (1, 2), self.student.pk: (0, 2), self.coach.pk: (0, 1), optional.pk: (2, 0)},
        )

        self.client.force_login(optional)
        response = self.client.get(self.url, {"plan": self.plan.pk})
        self.assertEqual(response.context["selected_plan"], self.plan)
        self.assertEqual([p["user_id"] for p in response.context["people"]], [optional.pk])
        self.assertContains(response, "已交 2 份 / 应交 0 份")

    def test_early_reading_assignments_do_not_supply_historical_competitors(self):
        self.grant("view_all_traininglog")
        legacy = self.make_plan("后补计划")
        day = legacy.schedule_days.create(date=self.first)
        for period, person in [("early", self.student), ("morning", self.user)]:
            TrainingCycleMember.objects.create(training_cycle=self.cycle_obj, user=person, role="competitor")
            slot = day.slots.create(period=period, kind="general")
            task = TrainingTask.objects.create(
                training_plan=legacy, planned_date=self.first, schedule_slot=slot, title=period,
                status=TrainingTask.Status.PUBLISHED, created_by=self.user,
            )
            task.executions.create(user=person)
            self.log(person, self.first)
        row = self.client.get(self.url, {"plan": legacy.pk}).context["rows"][0]
        self.assertEqual([person["name"] for person in row["submitted_competitors"]], ["张三"])

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
        self.assertEqual(row["unsubmitted_coaches"], ["李四"])

    def test_incomplete_roster_only_marks_affected_expected_counts_as_unknown(self):
        self.grant("view_all_traininglog")
        TrainingCycleMember.objects.create(training_cycle=self.cycle_obj, user=self.student, role="competitor")
        legacy = self.make_plan("历史缺少名单的计划")
        slot = legacy.schedule_days.create(date=self.first).slots.create(period="morning", kind="general")
        slot.coaches.add(self.coach, self.student)
        response = self.client.get(self.url, {"plan": legacy.pk})
        self.assertContains(response, "已交 0 份 / 应交待核定")
        self.assertContains(response, "已交 0 份 / 应交 1 份")
        self.assertEqual({p["name"]: p["expected"] for p in response.context["people"]}, {"李四": 1, "王五": None})
        self.assertEqual(response.context["rows"][0]["unsubmitted_coaches"], ["李四", "王五"])

    def test_historical_roster_confirmation_revocation_and_empty_roster(self):
        self.grant("view_trainingplan", "change_trainingplan", "view_all_traininglog")
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])
        TrainingCycleMember.objects.create(training_cycle=self.cycle_obj, user=self.student, role="competitor")
        legacy = self.make_plan("后补计划")
        legacy.participants.create(user=self.user, was_initial=True)
        for day, kind in [(self.first, "general"), (self.second, "rest"), (self.today, "general")]:
            legacy.schedule_days.create(date=day).slots.create(period="morning", kind=kind)
        url = reverse("training:historical_rosters", args=[legacy.pk])
        self.assertContains(self.client.get(url), "王五（已停用）")
        data = {"start": self.first, "end": self.second, "users": [self.student.pk], "reason": "训练签到表"}
        preview = self.client.post(url, data)
        self.assertEqual(preview.context["snapshot"]["dates"], [self.first.isoformat()])
        token = preview.context["token"]
        self.assertFalse(legacy.change_records.exists())
        self.assertRedirects(self.client.post(url, {"stage": "confirm", "token": token}), url)

        def row():
            return self.client.get(self.url, {"plan": legacy.pk}).context["rows"][0]

        self.assertEqual(row()["unsubmitted_competitors"], ["王五"])
        self.log(self.student, self.first)
        self.assertEqual([person["name"] for person in row()["submitted_competitors"]], ["王五"])
        self.assertEqual(row()["unsubmitted_competitors"], [])
        self.assertContains(self.client.post(url, data), "已补录的训练日")
        self.assertContains(self.client.post(url, data | {"end": self.today}), "早于今天")
        record = legacy.change_records.get(action=CONFIRMED)
        revoke = {"stage": "revoke", "record_id": record.pk, "reason": "依据有误"}
        self.assertRedirects(self.client.post(url, revoke), url)
        self.assertFalse(row()["roster_complete"])
        self.assertContains(self.client.post(url, {"stage": "confirm", "token": token}), "重新预览")
        self.assertEqual(legacy.change_records.filter(action=REVOKED).count(), 1)

        data["users"] = []
        self.assertContains(self.client.post(url, data), "请选择完整名单")
        empty_token = self.client.post(url, data | {"empty": "on"}).context["token"]
        self.assertRedirects(self.client.post(url, {"stage": "confirm", "token": empty_token}), url)
        self.assertTrue(row()["roster_complete"])
        self.assertEqual(row()["unsubmitted_competitors"], [])
        self.assertEqual(list(legacy.participants.values_list("user_id", flat=True)), [self.user.pk])

    def test_historical_roster_uses_existing_permission_and_cannot_replace_known_roster(self):
        self.grant("view_trainingplan", "view_all_traininglog")
        url = reverse("training:historical_rosters", args=[self.plan.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.grant("change_trainingplan")
        response = self.client.post(url, {
            "start": self.first, "end": self.second, "empty": "on", "reason": "测试",
        })
        self.assertContains(response, "没有需要补录名单的训练日")
        self.assertFalse(self.plan.change_records.filter(action=CONFIRMED).exists())

    def test_historical_roster_rechecks_training_days_after_preview(self):
        self.grant("view_trainingplan", "change_trainingplan")
        legacy = self.make_plan("后补计划")
        slot = legacy.schedule_days.create(date=self.first).slots.create(period="morning", kind="general")
        url = reverse("training:historical_rosters", args=[legacy.pk])
        preview = self.client.post(url, {
            "start": self.first, "end": self.first, "empty": "on", "reason": "训练签到表",
        })
        slot.kind = "rest"
        slot.save(update_fields=["kind"])
        response = self.client.post(url, {"stage": "confirm", "token": preview.context["token"]})
        self.assertContains(response, "没有需要补录名单的训练日")
        self.assertFalse(legacy.change_records.filter(action=CONFIRMED).exists())

    def test_same_log_counts_for_each_role_and_each_matching_plan(self):
        self.grant("view_all_traininglog")
        self.day(self.first, self.user, self.coach, period=TrainingScheduleSlot.Period.AFTERNOON)
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
        self.assertEqual(first["unsubmitted_coaches"], ["李四"])
        self.assertEqual(result["people"][0]["count"], 2)
        self.assertEqual(result["people"][0]["expected"], 3)
        self.assertEqual(training_log_submission_statistics(self.user, plan=overlap)["people"][0]["count"], 1)

    def test_filters_share_scope_in_chart_and_daily_table(self):
        self.grant("view_all_traininglog")
        self.log(self.user, self.second)
        response = self.client.get(
            self.url, {"q": "zs", "date_from": self.second.isoformat()}, headers={"HX-Request": "true"},
        )
        self.assertContains(response, "张三")
        self.assertContains(response, "已交 1 份 / 应交 1 份")
        self.assertContains(response, "未提交教练")
        self.assertNotContains(response, "重叠计划可各自计入同一份日志")
        self.assertNotContains(response, "王五")
        self.assertNotContains(response, "list-filter-search")
        self.assertEqual([row["date"] for row in response.context["rows"]], [self.second])
        self.assertEqual([p["count"] for p in response.context["people"]], [1])
        self.assertEqual(response.context["rows"][0]["unsubmitted_coaches"], [])
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

    def exemption_url(self):
        return reverse("training:plan_log_exemptions", args=[self.plan.pk])

    def exemption_preview(self, **data):
        return self.client.post(self.exemption_url(), {
            "operation": "add", "start": self.first.isoformat(), "reason": "训练安排", **data,
        })

    def exemption_confirm(self, response):
        return self.client.post(self.exemption_url(), {"token": response.context["token"]})

    def test_exemption_preview_only_reduces_named_coach_requirements(self):
        self.grant("view_all_traininglog")
        slot = self.plan.schedule_days.get(date=self.first).slots.get()
        slot.coaches_all = True
        slot.save(update_fields=["coaches_all"])
        self.plan.responsible_coaches.add(self.coach)
        self.client.force_login(User.objects.create_superuser("admin"))

        preview = self.exemption_preview(role="coach", end=self.second.isoformat())
        snapshot = preview.context["snapshot"]
        self.assertEqual(snapshot["delta"], -1)
        self.assertEqual([row["date"] for row in snapshot["rows"]], [self.second.isoformat()])
        self.assertRedirects(self.exemption_confirm(preview), self.exemption_url())
        first, second = self.stats()["rows"]
        self.assertEqual(first["exempt_coaches"], [])
        self.assertEqual(second["exempt_coaches"], ["李四"])

    def test_role_snapshot_and_overlapping_exemptions(self):
        self.grant("view_all_traininglog")
        self.plan.schedule_days.get(date=self.first).slots.get().coaches.add(self.student)
        log = self.log(self.student, self.first)
        self.plan.responsible_coaches.add(self.student)
        admin = User.objects.create_superuser("admin")
        self.client.force_login(admin)

        preview = self.exemption_preview(role="coach")
        self.assertContains(preview, "确认免交规则变更")
        self.assertEqual(preview.context["snapshot"]["delta"], -4)
        self.assertRedirects(self.exemption_confirm(preview), self.exemption_url())
        original = exemption_history(self.plan).get()
        self.assertEqual(original.actor, admin)
        self.plan.responsible_coaches.set([self.coach])
        first, second = self.stats()["rows"]
        self.assertEqual(first["exempt_competitors"], ["王五"])
        self.assertEqual(first["exempt_coaches"], ["王五"])
        self.assertEqual(first["submitted_coaches"][0]["log_id"], log.pk)
        self.assertEqual(second["unsubmitted_coaches"], ["李四"])
        student = next(person for person in self.stats()["people"] if person["user_id"] == self.student.pk)
        self.assertEqual((student["count"], student["expected"]), (2, 0))

        preview = self.exemption_preview(user=self.student.pk, start=self.second.isoformat())
        self.assertEqual(preview.context["snapshot"]["delta"], 0)
        self.assertRedirects(self.exemption_confirm(preview), self.exemption_url())
        preview = self.exemption_preview(
            operation="replace", target=original.pk, role="coach", start=self.second.isoformat(),
        )
        self.assertEqual(preview.context["snapshot"]["delta"], -2)
        self.assertRedirects(self.exemption_confirm(preview), self.exemption_url())
        replacement = exemption_history(self.plan).get(action=ACTIONS["replace"])
        self.assertEqual(replacement.before["names"], ["王五"])
        first, second = self.stats()["rows"]
        self.assertEqual(first["exempt_coaches"], ["王五"])
        self.assertEqual(second["exempt_competitors"], ["王五"])
        self.assertEqual(second["exempt_coaches"], ["李四"])
        self.assertEqual(second["unsubmitted_coaches"], [])

        preview = self.exemption_preview(operation="end", target=replacement.pk, start=self.second.isoformat())
        self.assertEqual(preview.context["snapshot"]["delta"], 2)
        self.assertRedirects(self.exemption_confirm(preview), self.exemption_url())
        first, second = self.stats()["rows"]
        self.assertEqual(first["exempt_coaches"], ["王五"])
        self.assertEqual(second["unsubmitted_coaches"], ["李四"])
        self.assertEqual(second["exempt_competitors"], ["王五"])

        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "免交选手")
        self.assertContains(response, "王五")

    def test_exemption_permissions_stale_preview_and_replay(self):
        url = self.exemption_url()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.exemption_preview(user=self.student.pk).status_code, 403)
        self.client.force_login(User.objects.create_superuser("admin"))
        self.assertContains(self.client.get(url), "预览变更")
        preview = self.exemption_preview(role="competitor")
        self.plan.participants.create(user=self.coach)
        self.assertContains(self.exemption_confirm(preview), "请重新预览")
        self.assertFalse(exemption_history(self.plan).exists())
        preview = self.exemption_preview(role="competitor")
        self.assertRedirects(self.exemption_confirm(preview), url)
        self.assertContains(self.exemption_confirm(preview), "请重新预览")
        self.assertEqual(exemption_history(self.plan).count(), 1)
        self.assertContains(self.exemption_preview(user=self.student.pk, start=self.plan.end_date + timedelta(days=1)),
                            "生效日期须在计划范围内")

    def test_exemption_candidates_are_limited_to_plan_rosters(self):
        duty_only = User.objects.create_user("duty-only", first_name="仅值班")
        withdrawn = User.objects.create_user("withdrawn", first_name="已退出")
        self.plan.duty_personnel.add(duty_only)
        self.plan.responsible_coaches.add(self.coach)
        self.plan.participants.create(user=withdrawn, is_active=False)
        search_url = reverse("training:plan_log_exemption_search", args=[self.plan.pk])
        self.assertEqual(self.client.get(search_url, {"q": "王五"}).status_code, 403)
        self.client.force_login(User.objects.create_superuser("admin"))

        response = self.client.get(self.exemption_url())
        self.assertContains(response, "负责教练")
        self.assertContains(response, "参与选手")
        candidates = response.context["form"].fields["user"].queryset
        self.assertEqual(set(candidates.values_list("pk", flat=True)), {self.user.pk, self.student.pk, self.coach.pk})
        self.assertEqual(self.client.get(search_url, {"q": "ww"}).json()["results"],
                         [{"id": self.student.pk, "label": "王五"}])
        self.assertEqual(self.client.get(search_url, {"q": "仅值班"}).json()["results"], [])
        for params in ({"user": duty_only.pk}, {"user": withdrawn.pk}, {"role": "duty"}):
            with self.subTest(params=params):
                response = self.exemption_preview(**params)
                self.assertTrue(response.context["form"].errors)
                self.assertNotIn("token", response.context)

        preview = self.exemption_preview(user=self.student.pk)
        self.plan.participants.filter(user=self.student).update(is_active=False)
        self.assertContains(self.exemption_confirm(preview), "已不在计划的负责教练或参与选手名单中")
        self.assertFalse(exemption_history(self.plan).exists())

    def test_exemption_combines_roles_and_multiple_people(self):
        self.plan.responsible_coaches.add(self.student, self.coach)
        self.client.force_login(User.objects.create_superuser("admin"))
        response = self.client.get(self.exemption_url())
        self.assertContains(response, "所有成员都会免交训练日志")
        self.assertContains(response, "全部负责教练")
        self.assertContains(response, "全部参与选手")

        for selection, expected in (
            ({"role": ["coach", "competitor"]}, [self.user, self.student, self.coach]),
            ({"role": ["coach"]}, [self.student, self.coach]),
            ({"role": ["competitor"]}, [self.user, self.student]),
            ({"user": [self.user.pk, self.student.pk]}, [self.user, self.student]),
            ({"role": ["coach"], "user": [self.user.pk, self.student.pk]}, [self.user, self.student, self.coach]),
        ):
            with self.subTest(selection=selection):
                preview = self.exemption_preview(**selection)
                rule = preview.context["snapshot"]["change"]["rule"]
                self.assertEqual(rule["user_ids"], sorted(user.pk for user in expected))
                self.assertContains(preview, f"合并后免交名单（{len(expected)} 人）")

        self.assertContains(preview, "指定人员 张三、王五")
        self.assertRedirects(self.exemption_confirm(preview), self.exemption_url())
        self.assertEqual(exemption_history(self.plan).get().after["rule"], rule)
