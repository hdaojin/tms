from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import scheduling as service
from .models import TrainingCycleMember, TrainingPlan, TrainingPlanParticipant, TrainingScheduleSlot, TrainingTaskCoach
from .schedule_forms import DayScheduleForm, SlotScheduleForm
from .tests import TrainingFixtureMixin, User, configure_test_periods


class EntryRefinementTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        configure_test_periods()
        self.clock = patch("django.utils.timezone.now", return_value=datetime(2026, 1, 1, tzinfo=dt_timezone.utc))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.cycle_obj = self.cycle()
        self.bind(self.cycle_obj)
        self.admin = User.objects.create_superuser("entry-admin")
        self.coach = User.objects.create_user("zhang", first_name="张教练")
        TrainingCycleMember.objects.create(training_cycle=self.cycle_obj, user=self.coach, role="coach")
        self.plan = TrainingPlan.objects.create(
            training_cycle=self.cycle_obj,
            title="分层计划",
            objective="训练",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
            created_by=self.admin,
        )
        self.plan.responsible_coaches.add(self.coach)
        self.plan.duty_personnel.add(self.coach)
        TrainingPlanParticipant.objects.create(training_plan=self.plan, user=User.objects.create_user("entry-athlete"))
        service.initialize_schedule(self.plan)
        self.plan.refresh_from_db()
        self.day = self.plan.schedule_days.first()
        self.slot = self.day.slots.get(period="morning")

    def publish_plan(self):
        self.plan.published_at = timezone.now()
        self.plan.save(update_fields=["published_at", "updated_at"])

    def save_slot(self, slot=None, kind="technical", reason=""):
        slot = slot or self.slot
        slot.refresh_from_db()
        before = service.slot_snapshot(slot)
        after = before | {
            "kind": kind,
            "domains": [self.linux.pk] if kind == "technical" else [],
            "primary_domain": self.linux.pk if kind == "technical" else None,
            "coaches": [self.coach.pk] if kind in service.ACTIVE_KINDS else [],
            "coaches_all": False,
        }
        return service.save_schedule(
            self.plan,
            self.admin,
            [{"type": "slot", "id": slot.pk, "revision": slot.revision, "before": before, "after": after}],
            reason,
        )

    def save_day(self, day=None, note="备注", reason=""):
        day = day or self.day
        day.refresh_from_db()
        before = service.day_snapshot(day)
        return service.save_schedule(
            self.plan,
            self.admin,
            [
                {
                    "type": "day",
                    "id": day.pk,
                    "revision": day.revision,
                    "before": before,
                    "after": before | {"duty_coaches": [self.coach.pk], "note": note},
                }
            ],
            reason,
        )

    def complete_schedule(self):
        for day in self.plan.schedule_days.all():
            if not service.was_filled(day):
                self.save_day(day)
            for slot in day.slots.filter(is_configured=True):
                if not service.was_filled(slot):
                    self.save_slot(slot, kind="rest")

    def test_stages_and_whole_schedule_completeness(self):
        with self.assertRaisesMessage(ValidationError, "先发布计划"):
            self.save_slot()
        self.publish_plan()
        self.save_slot()
        with self.assertRaises(ValidationError):
            service.publish_schedule(self.plan, self.admin)
        with self.assertRaises(PermissionDenied):
            service.save_slot_task(self.slot, self.admin, {"title": "不能提前填写"})
        self.complete_schedule()
        service.publish_schedule(self.plan, self.admin)
        slot = TrainingScheduleSlot.objects.select_related("day__training_plan").get(pk=self.slot.pk)
        task = service.save_slot_task(slot, self.admin, {"title": "排班发布后填写"})
        self.assertEqual(task.status, "draft")
        self.assertEqual(set(task.coach_links.values_list("user_id", flat=True)), {self.coach.pk})
        self.assertNotIn("role", {field.name for field in TrainingTaskCoach._meta.fields})

    def test_past_initial_entry_is_immediate_but_later_edit_requires_reason_and_approval(self):
        self.publish_plan()
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 4, tzinfo=dt_timezone.utc)):
            self.assertIsNone(self.save_slot())
            self.assertIsNone(self.save_day())
            self.slot.refresh_from_db()
            self.day.refresh_from_db()
            self.assertTrue(self.slot.has_been_filled)
            self.assertTrue(self.day.has_been_filled)
            self.assertFalse(self.plan.schedule_changes.exists())
            self.assertIsNone(self.save_day(note="草稿再次修改"))
            self.plan.schedule_published_at = timezone.now()
            self.plan.save(update_fields=["schedule_published_at", "updated_at"])
            with self.assertRaisesMessage(ValidationError, "调整原因"):
                self.save_day(note="第二次")
            change = self.save_day(note="第二次", reason="补正")
            self.assertEqual(change.status, "pending")
            self.day.refresh_from_db()
            self.assertEqual(self.day.note, "草稿再次修改")
            service.review_change(change, self.admin, approve=True)
            self.day.refresh_from_db()
            self.assertEqual(self.day.note, "第二次")

    def test_clearing_does_not_reset_initial_entry(self):
        self.publish_plan()
        self.save_slot()
        self.slot.domains.clear()
        self.slot.coaches.clear()
        TrainingScheduleSlot.objects.filter(pk=self.slot.pk).update(kind="pending", primary_domain=None)
        self.assertIsNone(self.save_slot())
        self.slot.refresh_from_db()
        self.assertTrue(self.slot.has_been_filled)

    def test_forms_require_domain_and_conditional_coaches_without_primary(self):
        data = {"object_id": self.slot.pk, "revision": 0, "domain_choice": "other"}
        form = SlotScheduleForm(data, plan=self.plan, initial={"period": "morning"})
        self.assertFalse(form.is_valid())
        rest = SlotScheduleForm(data | {"domain_choice": "rest"}, plan=self.plan, initial={"period": "morning"})
        self.assertTrue(rest.is_valid(), rest.errors)
        self.assertNotIn("primary_coach", rest.fields)
        duty = DayScheduleForm(
            {"object_id": self.day.pk, "revision": 0, "duty_all": True, "duty_coaches": [self.coach.pk]},
            plan=self.plan,
            initial={"date": self.day.date},
        )
        self.assertFalse(duty.is_valid())
        self.assertIn("张教练(zhang)", DayScheduleForm(plan=self.plan).as_p())

    def test_disabled_endpoints_and_compact_day_columns(self):
        self.client.force_login(self.admin)
        self.publish_plan()
        self.save_day(note="日级显示")
        response = self.client.get(
            reverse("training:plan_detail", args=[self.plan.pk]), {"sort": "-date", "primary_coach": "999"}
        )
        self.assertContains(response, "日级显示")
        columns = [column.name for column in response.context["table"].columns]
        self.assertNotIn("duty", columns)
        self.assertNotIn("note", columns)
        self.assertNotContains(response, 'name="primary_coach"')
        self.assertNotContains(response, 'name="sort"')
        self.assertEqual([row.date for row in response.context["table"].data], [date(2026, 1, 1), date(2026, 1, 2)])
        detail = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]), {"tab": "details"})
        self.assertIn("duty", [column.name for column in detail.context["table"].columns])
        for name in ("entry_operation", "schedule_swap", "schedule_bulk"):
            self.assertEqual(self.client.get(reverse(f"training:{name}", args=[self.plan.pk])).status_code, 403)

    def test_initial_reason_visibility_and_local_save(self):
        self.publish_plan()
        self.client.force_login(self.admin)
        url = reverse("training:schedule_edit", args=[self.plan.pk])
        params = {"days": self.day.pk, "slot": self.slot.pk}
        first = self.client.get(url, params, HTTP_HX_REQUEST="true")
        self.assertNotContains(first, 'name="reason"')
        self.assertNotContains(first, 'md:grid-cols-2')
        self.save_slot()
        second = self.client.get(url, params, HTTP_HX_REQUEST="true")
        self.assertNotContains(second, 'name="reason"')
        self.assertContains(second, '>保存</button>')

    def test_past_day_shading_and_natural_week_boundary(self):
        self.client.force_login(self.admin)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 2, 0, tzinfo=dt_timezone.utc)):
            response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
            days = response.context["entry_days"]
            self.assertTrue(days[0].is_past)
            self.assertFalse(days[1].is_past)
            self.assertFalse(days[0].week_past)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 5, 0, tzinfo=dt_timezone.utc)):
            response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
            self.assertTrue(response.context["entry_days"][0].week_past)

    def test_whole_rest_day_needs_no_duty_but_training_day_does(self):
        self.publish_plan()
        for index, slot in enumerate(self.plan.schedule_days.first().slots.filter(is_configured=True)):
            self.save_slot(slot=slot, kind="rest" if index % 2 else "unused")
        for slot in self.plan.schedule_days.last().slots.filter(is_configured=True):
            self.save_slot(slot=slot, kind="rest")
        service.publish_schedule(self.plan, self.admin)
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.schedule_published_at)

    def editor_data(self, response):
        data = {"days": self.day.pk, "action": "save"}
        for prefix in ("day", "slot"):
            forms = response.context[f"{prefix}_forms"]
            data[f"{prefix}-TOTAL_FORMS"] = len(forms)
            data[f"{prefix}-INITIAL_FORMS"] = len(forms)
            for form in forms:
                for field in form:
                    if field.field.disabled:
                        continue
                    value = field.value()
                    if value is not None and value is not False:
                        data[field.html_name] = "on" if value is True else value
        return data

    def test_day_editor_saves_all_slots_and_next_day_keeps_mode(self):
        self.publish_plan()
        self.client.force_login(self.admin)
        url = reverse("training:schedule_edit", args=[self.plan.pk])
        response = self.client.get(url, {"days": self.day.pk, "day_only": "1"}, HTTP_HX_REQUEST="true")
        forms = response.context["slot_forms"]
        self.assertEqual(len(forms), self.day.slots.filter(is_configured=True).count())
        self.assertContains(response, "全天同一安排")
        self.assertContains(response, "data-schedule-reset")
        self.assertNotContains(response, 'value="publish"')
        data = self.editor_data(response) | {"day_only": "1", "day-0-note": "全天休息"}
        for form in forms:
            data[f"{form.prefix}-domain_choice"] = "rest"
        saved = self.client.post(url, data, HTTP_HX_REQUEST="true")
        self.assertContains(saved, "继续下一天")
        self.assertIn("day_only=1", saved.context["next_query"])
        self.assertFalse(self.day.slots.filter(is_configured=True).exclude(kind="rest").exists())
        self.day.refresh_from_db()
        self.assertEqual(self.day.note, "全天休息")
        next_day = self.plan.schedule_days.last()
        following = self.client.get(url, {"days": next_day.pk, "day_only": "1"}, HTTP_HX_REQUEST="true")
        self.assertEqual(len(following.context["slot_forms"]), next_day.slots.filter(is_configured=True).count())
        self.assertEqual(following.context["day_forms"][0].initial["note"], "")
        self.assertEqual(self.client.post(url, data | {"action": "publish"}).status_code, 403)

    def test_slot_editor_next_day_and_display_names(self):
        self.publish_plan()
        self.client.force_login(self.admin)
        url = reverse("training:schedule_edit", args=[self.plan.pk])
        response = self.client.get(url, {"days": self.day.pk, "slot": self.slot.pk}, HTTP_HX_REQUEST="true")
        data = self.editor_data(response) | {"slot": self.slot.pk, "slot-0-domain_choice": str(self.linux.pk), "slot-0-coaches": [self.coach.pk]}
        saved = self.client.post(url, data, HTTP_HX_REQUEST="true")
        next_slot = self.plan.schedule_days.last().slots.get(period=self.slot.period)
        self.assertEqual(saved.context["next_query"], f"days={next_slot.day_id}&slot={next_slot.pk}")
        self.save_day()
        for tab in ("schedule", "details"):
            page = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]), {"tab": tab})
            rows = page.context["entry_days"]
            self.assertIn("张教练", str(rows[0].duty_label))
            self.assertNotIn("zhang", str(rows[0].duty_label))
            slot = next(item for item in rows[0].slots.all() if item.pk == self.slot.pk)
            self.assertNotIn("zhang", str(slot.coach_label))

    def test_expired_draft_task_edits_and_skills_save_without_reason(self):
        from .schedule_forms import SlotTaskForm
        self.publish_plan()
        self.save_slot()
        self.complete_schedule()
        service.publish_schedule(self.plan, self.admin)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 4, tzinfo=dt_timezone.utc)):
            task = service.save_slot_task(self.slot, self.admin, {"title": "过期草稿"})
            saved = service.save_slot_task(self.slot, self.admin, {"title": "无需原因"}, task=task)
            self.assertEqual(saved.title, "无需原因")
            self.assertFalse(self.plan.schedule_changes.exists())
            self.assertNotIn("reason", SlotTaskForm(instance=saved, slot=self.slot).fields)
            service.set_task_skills(saved, self.admin, [])
            self.assertFalse(self.plan.schedule_changes.exists())

    def test_weekday_filter_and_invalid_weekday(self):
        self.client.force_login(self.admin)
        url = reverse("training:plan_detail", args=[self.plan.pk])
        page = self.client.get(url, {"weekday": ["3", "4"]})
        self.assertEqual([day.date.weekday() for day in page.context["entry_days"]], [3, 4])
        page = self.client.get(url, {"weekday": ["4"], "tab": "details"}, HTTP_HX_REQUEST="true")
        self.assertEqual([day.date.weekday() for day in page.context["entry_days"]], [4])
        self.assertEqual(len(page.context["table"].data), 4)
        invalid = self.client.get(url, {"weekday": ["7"]})
        self.assertEqual(invalid.context["entry_days"], [])

    def test_next_entry_filters_all_dates_and_requires_corresponding_slot(self):
        from types import SimpleNamespace
        from django.http import QueryDict
        from .entry_navigation import next_entry
        long_cycle = self.cycle("LONG", end_date=date(2026, 3, 1))
        self.bind(long_cycle)
        self.plan = TrainingPlan.objects.create(training_cycle=long_cycle, title="跨页计划", objective="测试筛选", start_date=date(2026, 1, 1), end_date=date(2026, 3, 1), created_by=self.admin)
        service.initialize_schedule(self.plan)
        self.plan.refresh_from_db()
        self.publish_plan()
        # 从31个匹配日期之后继续，不能只查询第一页。
        params = QueryDict("weekday=0&weekday=1&weekday=2&weekday=3&weekday=4&weekday=5&weekday=6&period=afternoon&date_from=2026-01-01")
        request = SimpleNamespace(user=self.admin, method="GET", GET=params)
        current = self.plan.schedule_days.get(date=date(2026, 2, 5))
        following = next_entry(request, self.plan, current, period="afternoon")
        self.assertEqual(following["day"].date, date(2026, 2, 6))
        self.assertIn("entry_filters=", following["url"])
        self.assertIsNone(next_entry(request, self.plan, current, period="morning"))
        request.GET = params.copy()
        request.GET["date_to"] = "2026-02-05"
        self.assertIsNone(next_entry(request, self.plan, current, period="afternoon"))

    def test_filtered_save_carries_context_to_next_editor_and_reset(self):
        self.publish_plan()
        self.client.force_login(self.admin)
        url = reverse("training:schedule_edit", args=[self.plan.pk])
        filters = "weekday=3&weekday=4&period=morning&state=pending"
        response = self.client.get(url, {"days": self.day.pk, "slot": self.slot.pk, "entry_filters": filters}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.context["entry_filters"], filters)
        data = self.editor_data(response) | {"slot": self.slot.pk, "entry_filters": filters, "slot-0-domain_choice": "rest"}
        saved = self.client.post(url, data, HTTP_HX_REQUEST="true")
        self.assertEqual(saved.context["next_day"].date, date(2026, 1, 2))
        self.assertIn("entry_filters=", saved.context["next_query"])

    def test_task_next_day_keeps_filters_and_opens_new_task(self):
        self.publish_plan()
        self.save_slot()
        next_slot = self.plan.schedule_days.last().slots.get(period="morning")
        self.save_slot(next_slot)
        self.complete_schedule()
        service.publish_schedule(self.plan, self.admin)
        self.client.force_login(self.admin)
        filters = "weekday=3&weekday=4&period=morning&domain=" + str(self.linux.pk)
        response = self.client.post(reverse("training:slot_task_create", args=[self.slot.pk]), {"title": "筛选任务", "entry_filters": filters, "action": "save"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "继续下一天")
        following = response.context["next_entry"]
        self.assertEqual(following["day"].date, next_slot.day.date)
        self.assertIn(reverse("training:slot_task_create", args=[next_slot.pk]), following["url"])
        self.assertFalse(next_slot.tasks.exists())
        editor = self.client.get(following["url"], HTTP_HX_REQUEST="true")
        self.assertIsNone(editor.context["task"])
        self.assertEqual(editor.context["entry_filters"], filters)

    def test_change_history_paginates_ten_independently_of_entries(self):
        from .models import TrainingChangeRecord
        TrainingChangeRecord.objects.bulk_create([
            TrainingChangeRecord(training_plan=self.plan, actor=self.admin, action=f"历史 {index}")
            for index in range(23)
        ])
        self.client.force_login(self.admin)
        url = reverse("training:plan_detail", args=[self.plan.pk])
        expected = list(self.plan.change_records.values_list("pk", flat=True))
        first = self.client.get(url, {"tab": "details", "weekday": ["3", "4"]})
        self.assertEqual([record.pk for record in first.context["history"]], expected[:10])
        self.assertContains(first, "变更历史分页")
        self.assertContains(first, "history_page=2")
        self.assertContains(first, "tab=details")
        second = self.client.get(url, {"tab": "details", "history_page": 2, "weekday": ["3", "4"]}, HTTP_HX_REQUEST="true")
        self.assertEqual([record.pk for record in second.context["history"]], expected[10:20])
        self.assertEqual([day.pk for day in second.context["entry_days"]], [day.pk for day in first.context["entry_days"]])
        last = self.client.get(url, {"history_page": 999})
        self.assertEqual([record.pk for record in last.context["history"]], expected[20:])
