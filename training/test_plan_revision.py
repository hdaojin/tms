from datetime import date, datetime, time, timezone as dt_timezone
from importlib import import_module
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from . import scheduling
from .admin import TrainingPeriodConfigAdminForm
from .forms import TrainingPlanForm
from .models import TrainingCycleMember, TrainingPeriodConfig, TrainingPlan, TrainingPlanParticipant, TrainingScheduleSlot
from .plan_workbooks import build_plan_workbook, preview_import
from .tests import TrainingFixtureMixin, User


class PlanRevisionTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.clock = patch("django.utils.timezone.now", return_value=datetime(2026, 1, 1, 0, tzinfo=dt_timezone.utc))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.cycle_obj = self.cycle()
        self.bind(self.cycle_obj)
        self.admin = User.objects.create_superuser("plan-revision-admin")
        self.client.force_login(self.admin)

    def values(self, **overrides):
        return {
            "training_cycle": self.cycle_obj.pk, "title": "新训练计划",
            "start_date": "2026-01-01", "end_date": "2026-01-02", "objective": "训练",
            "early_start": "08:10", "early_end": "08:50",
            "morning_start": "09:00", "morning_end": "12:00",
            "afternoon_start": "14:00", "afternoon_end": "16:30",
            "evening_start": "18:30", "evening_end": "20:30",
            **overrides,
        }

    def create_plan(self, **overrides):
        response = self.client.post(reverse("training:plan_create"), self.values(**overrides))
        self.assertEqual(response.status_code, 302, response.context["form"].errors if response.context else "")
        return TrainingPlan.objects.get(title=overrides.get("title", "新训练计划"))

    def test_defaults_are_persisted_and_admin_rejects_overlaps(self):
        defaults = dict(TrainingPeriodConfig.objects.values_list("period", "start_time"))
        self.assertEqual(defaults["early"], time(8, 10))
        morning = TrainingPeriodConfig.objects.get(period="morning")
        form = TrainingPeriodConfigAdminForm({"start_time": "08:30", "end_time": "12:00"}, instance=morning)
        self.assertFalse(form.is_valid())
        response = self.client.get(reverse("training:plan_create"))
        self.assertEqual(response.context["form"].initial["evening_end"], time(20, 30))
        self.assertEqual(self.client.get(reverse("admin:training_trainingperiodconfig_change", args=[morning.pk])).status_code, 200)

    def test_updated_default_only_affects_new_plan(self):
        plan = self.create_plan()
        TrainingPeriodConfig.objects.filter(period="early").update(start_time=time(8, 15))
        response = self.client.get(reverse("training:plan_create"))
        self.assertEqual(response.context["form"].initial["early_start"], time(8, 15))
        plan.refresh_from_db()
        self.assertEqual(plan.early_start, time(8, 10))

    def test_migration_preserves_existing_defaults_and_only_adds_missing(self):
        TrainingPeriodConfig.objects.filter(period="early").update(start_time=time(7, 30), end_time=time(8))
        TrainingPeriodConfig.objects.filter(period="evening").delete()
        migration = import_module("training.migrations.0015_optional_schedule_periods")
        migration.add_default_periods(apps, SimpleNamespace(connection=SimpleNamespace(alias="default")))
        self.assertEqual(TrainingPeriodConfig.objects.get(period="early").start_time, time(7, 30))
        self.assertEqual(TrainingPeriodConfig.objects.get(period="evening").start_time, time(18, 30))

    def test_roster_migration_preserves_existing_assignments(self):
        plan = self.create_plan()
        day = plan.schedule_days.first()
        coach = User.objects.create_user("historic-coach")
        duty = User.objects.create_user("historic-duty")
        slot = day.slots.get(period="morning")
        slot.coaches.add(coach)
        day.duty_coaches.add(duty)
        migration = import_module("training.migrations.0019_plan_rosters")
        migration.populate_rosters(apps, SimpleNamespace(connection=SimpleNamespace(alias="default")))
        self.assertEqual(list(plan.responsible_coaches.all()), [coach])
        self.assertEqual(list(plan.duty_personnel.all()), [duty])
        self.assertEqual(list(slot.coaches.all()), [coach])
        self.assertEqual(list(day.duty_coaches.all()), [duty])

    def test_edit_preserves_historical_file_and_manager_relationship(self):
        plan = self.create_plan()
        old_manager = User.objects.create_user("historic-manager")
        plan.task_managers.add(old_manager)
        plan.source_file = "historical/plan.xlsx"
        plan.save()
        form = TrainingPlanForm(self.values(title="编辑训练计划"), instance=plan)
        self.assertTrue(form.is_valid(), form.errors)
        scheduling.save_plan_definition(form, self.admin)
        plan.refresh_from_db()
        self.assertEqual(plan.source_file.name, "historical/plan.xlsx")
        self.assertTrue(plan.task_managers.filter(pk=old_manager.pk).exists())

    def test_empty_optional_periods_and_people_can_be_saved_as_draft(self):
        plan = self.create_plan(early_start="", early_end="", evening_start="", evening_end="")
        self.assertIsNone(plan.published_at)
        self.assertFalse(plan.schedulers.exists())
        self.assertFalse(plan.participants.exists())
        self.assertEqual(plan.schedule_days.count(), 2)
        self.assertEqual(TrainingScheduleSlot.objects.filter(day__training_plan=plan, is_configured=False).count(), 4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrainingScheduleSlot.objects.filter(day__training_plan=plan, period="early").update(kind="general")
        with self.assertRaises(ValidationError):
            scheduling.publish_schedule(plan, self.admin)
        response = self.client.get(reverse("training:plan_detail", args=[plan.pk]))
        self.assertEqual(response.status_code, 200)
        table = response.context["table"]
        self.assertIn("early", [column.name for column in table.columns])
        self.assertIn("evening", [column.name for column in table.columns])
        swap = self.client.get(reverse("training:schedule_swap", args=[plan.pk]))
        self.assertEqual(swap.status_code, 403)

    def test_half_optional_period_is_invalid(self):
        form = TrainingPlanForm(self.values(early_start="08:10", early_end=""))
        self.assertFalse(form.is_valid())
        form = TrainingPlanForm(self.values(morning_start="", morning_end=""))
        self.assertFalse(form.is_valid())
        form = TrainingPlanForm(self.values(end_date=""))
        self.assertFalse(form.is_valid())

    def test_empty_draft_time_change_updates_all_framework_days(self):
        plan = self.create_plan()
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 1, 4, tzinfo=dt_timezone.utc)):
            values = self.values(early_start="", early_end="")
            form = TrainingPlanForm(values, instance=plan)
            self.assertTrue(form.is_valid(), form.errors)
            scheduling.save_plan_definition(form, self.admin)
        old = plan.schedule_days.get(date=date(2026, 1, 1)).slots.get(period="early")
        future = plan.schedule_days.get(date=date(2026, 1, 2)).slots.get(period="early")
        self.assertFalse(old.is_configured)
        self.assertFalse(future.is_configured)
        workbook = load_workbook(BytesIO(build_plan_workbook(plan)))
        labels = [workbook["训练计划"].cell(row, 3).value for row in range(3, workbook["训练计划"].max_row + 1)]
        self.assertEqual(labels.count("早读"), 0)

    def test_disable_does_not_remove_existing_future_arrangements(self):
        plan = self.create_plan()
        future = plan.schedule_days.get(date=date(2026, 1, 2)).slots.get(period="early")
        future.kind = "rest"
        future.save()
        form = TrainingPlanForm(self.values(early_start="", early_end=""), instance=plan)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.fields["early_start"].disabled)
        scheduling.save_plan_definition(form, self.admin)
        future.refresh_from_db()
        self.assertTrue(future.is_configured)
        self.assertEqual(future.kind, "rest")

    def test_empty_draft_date_change_synchronizes_framework(self):
        plan = self.create_plan()
        form = TrainingPlanForm(self.values(start_date="2026-01-02"), instance=plan)
        self.assertTrue(form.is_valid(), form.errors)
        updated = scheduling.save_plan_definition(form, self.admin)
        self.assertEqual(list(updated.schedule_days.values_list("date", flat=True)), [date(2026, 1, 2)])
        self.assertEqual(updated.schedule_days.get().slots.count(), 4)

    def test_structure_edit_preserves_cancelled_task_references(self):
        plan = self.create_plan()
        slot = plan.schedule_days.get(date=plan.start_date).slots.get(period="morning")
        task = plan.tasks.create(
            title="已取消任务", planned_date=plan.start_date, schedule_slot=slot,
            status="cancelled", created_by=self.admin,
        )
        form = TrainingPlanForm(self.values(start_date="2026-01-02"), instance=plan)
        self.assertFalse(form.is_valid())
        self.assertIn("已有历史任务", str(form.errors))
        plan.refresh_from_db()
        form = TrainingPlanForm(self.values(morning_start="09:30"), instance=plan)
        self.assertFalse(form.is_valid())
        self.assertIn("已关联历史任务", str(form.errors))
        plan.refresh_from_db()
        form = TrainingPlanForm(self.values(afternoon_start="14:30"), instance=plan)
        self.assertTrue(form.is_valid(), form.errors)
        scheduling.save_plan_definition(form, self.admin)
        task.refresh_from_db()
        self.assertEqual(task.schedule_slot_id, slot.pk)
        self.assertEqual(task.schedule_slot.starts_at, slot.starts_at)

    def test_disable_unknown_times_in_empty_draft(self):
        plan = self.create_plan()
        TrainingScheduleSlot.objects.filter(day__training_plan=plan, period="early").update(starts_at=None, ends_at=None)
        form = TrainingPlanForm(self.values(early_start="", early_end=""), instance=plan)
        self.assertTrue(form.is_valid(), form.errors)
        scheduling.save_plan_definition(form, self.admin)
        self.assertFalse(plan.schedule_days.get(date=date(2026, 1, 1)).slots.get(period="early").is_configured)
        self.assertFalse(plan.schedule_days.get(date=date(2026, 1, 2)).slots.get(period="early").is_configured)

    def test_workbooks_hide_disabled_periods_and_reject_filled_disabled_rows(self):
        plan = self.create_plan(early_start="", early_end="", evening_start="", evening_end="")
        TrainingCycleMember.objects.create(training_cycle=self.cycle_obj, user=self.admin, role="coach")
        TrainingPlanParticipant.objects.create(training_plan=plan, user=User.objects.create_user("revision-athlete"))
        plan.responsible_coaches.add(self.admin)
        plan.duty_personnel.add(self.admin)
        plan.published_at = timezone.now()
        plan.save(update_fields=["published_at"])
        export = load_workbook(BytesIO(build_plan_workbook(plan)))
        labels = [export["训练计划"].cell(row, 3).value for row in range(3, export["训练计划"].max_row + 1)]
        self.assertEqual(labels, ["上午", "下午", "上午", "下午"])
        template = load_workbook(BytesIO(build_plan_workbook(plan, import_template=True)))
        self.assertEqual(template["训练计划"].max_row, 10)
        self.assertIn("未设置", template["填写说明"]["A2"].value)
        template["训练计划"]["D3"] = "综合活动"
        output = BytesIO()
        template.save(output)
        records, _ = preview_import(plan, self.admin, BytesIO(output.getvalue()))
        self.assertEqual(records[0]["status"], "错误")
        self.assertIn("未设置", records[0]["message"])
        self.assertEqual(self.client.get(reverse("training:plan_import_template", args=[plan.pk])).status_code, 200)

    def test_scheduler_permissions_and_legacy_role(self):
        plan = self.create_plan()
        scheduler = User.objects.create_user("scheduler")
        old_manager = User.objects.create_user("old-manager")
        perms = Permission.objects.filter(content_type__app_label="training", codename__in=[
            "schedule_trainingplan", "change_trainingplan", "add_trainingtask", "change_trainingtask", "view_trainingplan"
        ])
        scheduler.user_permissions.add(*perms)
        old_manager.user_permissions.add(*perms)
        plan.schedulers.add(scheduler)
        plan.task_managers.add(old_manager)
        slot = plan.schedule_days.first().slots.get(period="morning")
        slot.kind = "general"
        slot.save()
        slot.day.training_plan = plan
        self.assertTrue(scheduling.plan_manager(scheduler, plan))
        self.assertFalse(scheduling.can_fill(scheduler, slot, create=True))
        TrainingCycleMember.objects.create(training_cycle=plan.training_cycle, user=scheduler, role="coach")
        plan.responsible_coaches.add(scheduler)
        plan.duty_personnel.add(scheduler)
        TrainingPlanParticipant.objects.create(training_plan=plan, user=User.objects.create_user("scheduler-athlete"))
        plan.published_at = timezone.now()
        plan.save()
        for day in plan.schedule_days.all():
            day.duty_coaches.add(scheduler)
            day.slots.exclude(pk=slot.pk).update(kind="rest")
        slot.coaches.add(scheduler)
        scheduling.publish_schedule(plan, self.admin)
        plan.refresh_from_db()
        slot.day.training_plan = plan
        self.assertTrue(scheduling.can_fill(scheduler, slot, create=True))
        self.assertFalse(scheduling.plan_manager(old_manager, plan))
        self.assertFalse(scheduling.visible_plans(old_manager).filter(pk=plan.pk).exists())
        scheduler.user_permissions.remove(Permission.objects.get(content_type__app_label="training", codename="schedule_trainingplan"))
        scheduler = User.objects.get(pk=scheduler.pk)
        self.assertFalse(scheduling.plan_manager(scheduler, plan))

    def test_new_person_requires_permission_but_existing_selection_is_retained(self):
        person = User.objects.create_user("ineligible")
        form = TrainingPlanForm(self.values(schedulers=[person.pk]))
        self.assertFalse(form.is_valid())
        search = self.client.get(reverse("training:plan_staff_search"), {"role": "schedulers", "q": "ineligible"})
        self.assertEqual(search.json()["results"], [])
        self.assertEqual(self.client.post(reverse("training:plan_create"), self.values(schedulers=[person.pk])).status_code, 200)
        self.assertFalse(TrainingPlan.objects.filter(title="新训练计划").exists())
        plan = self.create_plan()
        plan.schedulers.add(person)
        form = TrainingPlanForm(self.values(schedulers=[person.pk]), instance=plan)
        self.assertTrue(form.is_valid(), form.errors)
