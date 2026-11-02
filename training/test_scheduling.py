from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch
from io import BytesIO

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from standards.models import Skill
from .models import (
    TaskExecution,
    TrainingCycleMember,
    TrainingPlan,
    TrainingScheduleDay,
    TrainingScheduleSlot,
    TrainingTask,
)
from . import scheduling as service
from .schedule_export import build_plan_workbook
from .selectors import manageable_training_tasks_for, visible_training_tasks_for
from .services import update_execution_facts
from .tests import TrainingFixtureMixin, User, configure_test_periods


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ScheduleTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        configure_test_periods()
        self.clock = patch("django.utils.timezone.now", return_value=datetime(2026, 1, 1, 0, tzinfo=dt_timezone.utc))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.cycle_obj = self.cycle()
        self.bind(self.cycle_obj)
        self.admin = User.objects.create_superuser("schedule-admin", password="test")
        self.coach = self.person("coach", "coach", ["add_trainingtask", "change_trainingtask"])
        self.collaborator = self.person("collaborator", "coach", ["add_trainingtask", "change_trainingtask"])
        self.student = self.person("student", "competitor")
        self.student2 = self.person("student2", "competitor")
        self.scheduler = self.person(
            "scheduler", "coach", ["schedule_trainingplan", "add_trainingtask", "change_trainingtask"]
        )
        self.approver = self.person("approver", "coach", ["approve_trainingplan"])
        self.plan = TrainingPlan.objects.create(
            training_cycle=self.cycle_obj,
            title="一月训练计划",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
            objective="训练",
            created_by=self.admin,
        )
        self.plan.schedulers.add(self.scheduler)
        self.plan.approvers.add(self.approver)
        from .models import TrainingPlanParticipant
        for student in (self.student, self.student2):
            TrainingPlanParticipant.objects.create(training_plan=self.plan, user=student, was_initial=True)
        service.initialize_schedule(self.plan)
        self.plan.refresh_from_db()
        self.day = self.plan.schedule_days.get(date=date(2026, 1, 1))
        self.slot = self.day.slots.get(period="morning")

    def person(self, username, role, permissions=()):
        user = User.objects.create_user(username, password="test", first_name=username)
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="training",
                codename__in=["view_trainingplan", "view_trainingtask", "view_taskexecution", "change_taskexecution", *permissions],
            )
        )
        TrainingCycleMember.objects.create(training_cycle=self.cycle_obj, user=user, role=role)
        return user

    def ready(self, *, publish=True, all_coaches=False, general=False):
        self.plan.published_at = timezone.now()
        self.plan.save()
        for day in self.plan.schedule_days.all():
            day.duty_coaches.add(self.coach)
        TrainingScheduleSlot.objects.filter(day__training_plan=self.plan).update(kind="unused")
        self.slot.kind = "general" if general else "technical"
        self.slot.coaches_all = all_coaches
        self.slot.primary_domain = None if general else self.linux
        self.slot.save()
        self.slot.coaches.set([] if all_coaches else [self.coach, self.collaborator])
        if not general:
            self.slot.domains.add(self.linux)
        self.day.duty_all = True
        self.day.save()
        if publish:
            service.publish_schedule(self.plan, self.scheduler)
            self.plan.refresh_from_db()
            self.plan.published_at = timezone.now()
            self.plan.save()
            self.day.refresh_from_db()
            self.slot = TrainingScheduleSlot.objects.select_related("day__training_plan").get(pk=self.slot.pk)

    def new_task(self, **values):
        return service.save_slot_task(
            self.slot, self.coach, {"title": "部署服务", "skills": [], "competitors": [], **values}, publish=True
        )

    def change_slot(self, slot=None, **values):
        slot = slot or self.slot
        slot.refresh_from_db()
        before = service.slot_snapshot(slot)
        return {"type": "slot", "id": slot.pk, "revision": slot.revision, "before": before, "after": before | values}

    def test_framework_idempotent_unique_and_defaults(self):
        service.initialize_schedule(self.plan)
        self.assertEqual(self.plan.schedule_days.count(), 2)
        self.assertEqual(TrainingScheduleSlot.objects.filter(day__training_plan=self.plan).count(), 8)
        self.assertEqual(self.day.slots.get(period="early").kind, "pending")
        self.assertEqual(self.slot.kind, "pending")
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrainingScheduleSlot.objects.create(day=self.day, period="morning")
        with self.assertRaises(ValidationError):
            TrainingScheduleDay(training_plan=self.plan, date=date(2026, 2, 1)).full_clean()

    def test_publish_accepts_multiple_equal_coaches(self):
        self.ready(publish=False)
        service.publish_schedule(self.plan, self.scheduler)
        self.assertEqual(self.slot.coaches.count(), 2)

    def test_all_coaches_and_duty_snapshot_at_publish(self):
        self.ready(all_coaches=True)
        expected = service.coach_ids(self.plan)
        self.assertSetEqual(set(self.slot.coaches.values_list("pk", flat=True)), expected)
        self.day.refresh_from_db()
        self.assertSetEqual(set(self.day.duty_coaches.values_list("pk", flat=True)), expected)
        later = self.person("later-coach", "coach")
        self.assertNotIn(later.pk, self.slot.coaches.values_list("pk", flat=True))
        self.assertTrue(service.can_fill(self.scheduler, self.slot, create=True))
        self.assertTrue(service.can_fill(self.coach, self.slot, create=True))

    def test_plain_title_and_no_skill_publishes_to_all_snapshot(self):
        self.ready()
        task = self.new_task()
        self.assertEqual(task.requirements, "")
        self.assertFalse(task.skill_links.exists())
        service.publish_slot_task(task, self.coach)
        self.assertSetEqual(set(task.executions.values_list("user_id", flat=True)), {self.student.pk, self.student2.pk})
        later = self.person("later-student", "competitor")
        task.refresh_from_db()
        service.save_slot_task(
            self.slot,
            self.coach,
            {
                "title": "更新标题",
                "competitors": list(task.selected_competitors.values_list("pk", flat=True)),
                "skills": [],
            },
            task=task,
        )
        self.assertFalse(task.executions.filter(user=later).exists())

    def test_general_activity_has_execution_without_domains(self):
        self.ready(general=True)
        task = self.new_task()
        service.publish_slot_task(task, self.coach)
        self.assertEqual(task.executions.count(), 2)
        self.assertFalse(task.domain_links.exists())

    def test_collaborator_can_edit_and_publish_assigned_slot(self):
        self.ready()
        task = self.new_task()
        self.assertTrue(manageable_training_tasks_for(self.collaborator).filter(pk=task.pk).exists())
        service.save_slot_task(self.slot, self.collaborator, {"title": "协作任务"}, task=task)
        service.publish_slot_task(task, self.collaborator)
        self.slot.coaches.remove(self.collaborator)
        with self.assertRaises(PermissionDenied):
            service.publish_slot_task(task, self.collaborator)

    def test_plan_members_see_published_tasks_not_drafts(self):
        self.ready()
        task = self.new_task()
        self.assertTrue(visible_training_tasks_for(self.student).filter(pk=task.pk).exists())
        self.assertTrue(visible_training_tasks_for(self.collaborator).filter(pk=task.pk).exists())
        service.publish_slot_task(task, self.coach)
        self.assertTrue(visible_training_tasks_for(self.student).filter(pk=task.pk).exists())
        outsider = User.objects.create_user("outsider")
        outsider.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="training", codename__in=["view_trainingplan", "view_trainingtask"]
            )
        )
        self.assertFalse(service.visible_plans(outsider).exists())
        self.assertFalse(visible_training_tasks_for(outsider).exists())

    def test_permission_without_plan_role_cannot_schedule_or_approve(self):
        self.ready()
        outsider = self.person("unassigned", "coach", ["schedule_trainingplan", "approve_trainingplan"])
        with self.assertRaises(PermissionDenied):
            service.save_schedule(
                self.plan,
                outsider,
                [self.change_slot(coaches=[self.collaborator.pk])],
                "调班",
            )
        change = service.save_schedule(
            self.plan,
            self.scheduler,
            [self.change_slot(coaches=[self.collaborator.pk])],
            "调班",
        )
        with self.assertRaises(PermissionDenied):
            service.review_change(change, outsider, approve=True)

    def test_approval_handoff_preserves_author_and_history(self):
        self.ready()
        task = self.new_task()
        change = service.save_schedule(
            self.plan,
            self.scheduler,
            [self.change_slot(coaches=[self.collaborator.pk])],
            "人员交接",
        )
        self.slot.refresh_from_db()
        self.assertIn(self.coach.pk, self.slot.coaches.values_list("pk", flat=True))
        self.confirm_change_coaches(change)
        service.review_change(change, self.approver, approve=True)
        self.slot.refresh_from_db()
        self.assertIn(self.collaborator.pk, self.slot.coaches.values_list("pk", flat=True))
        self.assertFalse(service.can_fill(self.coach, self.slot))
        self.assertTrue(service.can_fill(self.collaborator, self.slot))
        task.refresh_from_db()
        self.assertEqual(task.created_by_id, self.coach.pk)
        self.assertEqual(task.coach_links.get().user_id, self.collaborator.pk)
        self.assertTrue(self.plan.change_records.filter(action="批准调整").exists())
        with self.assertRaisesMessage(ValidationError, "重复"):
            self.confirm_change_coaches(change)
            service.review_change(change, self.approver, approve=True)

    def test_rejection_and_stale_approval_never_apply(self):
        self.ready()
        payload = [self.change_slot(coaches=[self.collaborator.pk])]
        rejected = service.save_schedule(self.plan, self.scheduler, payload, "申请一")
        stale = service.save_schedule(self.plan, self.scheduler, payload, "申请二")
        self.confirm_change_coaches(rejected)
        service.review_change(rejected, self.approver, approve=False, note="不调整")
        self.slot.refresh_from_db()
        self.assertIn(self.coach.pk, self.slot.coaches.values_list("pk", flat=True))
        actual = service.save_schedule(self.plan, self.scheduler, payload, "申请三")
        self.confirm_change_coaches(actual)
        service.review_change(actual, self.approver, approve=True)
        with self.assertRaisesMessage(ValidationError, "已经变化"):
            self.confirm_change_coaches(stale)
            service.review_change(stale, self.approver, approve=True)
        stale.refresh_from_db()
        self.assertEqual(stale.status, "pending")

    def test_requester_permission_revocation_is_rechecked(self):
        self.ready()
        change = service.save_schedule(
            self.plan,
            self.scheduler,
            [self.change_slot(coaches=[self.collaborator.pk])],
            "待审交接",
        )
        self.plan.schedulers.remove(self.scheduler)
        with self.assertRaisesMessage(ValidationError, "申请人已无"):
            self.confirm_change_coaches(change)
            service.review_change(change, self.approver, approve=True)
        self.slot.refresh_from_db()
        self.assertIn(self.coach.pk, self.slot.coaches.values_list("pk", flat=True))

    def test_draft_and_cancelled_tasks_cannot_allocate_executions(self):
        self.ready()
        task = TrainingTask.objects.create(training_plan=self.plan, schedule_slot=self.slot, planned_date=self.day.date, title="历史草稿", created_by=self.coach)
        with self.assertRaisesMessage(ValidationError, "已发布任务"):
            service.assign_competitors(task, self.coach, reason="调整名单", selected=[self.student.pk])
        self.assertFalse(task.executions.exists())
        service.publish_slot_task(task, self.coach)
        task.status = "draft"
        task.save(update_fields=["status", "updated_at"])
        service.cancel_task(task, self.coach, "取消")
        with self.assertRaisesMessage(ValidationError, "已发布任务"):
            service.assign_competitors(task, self.coach, reason="调整名单", selected=[self.student.pk])

    def test_self_approval_is_allowed_with_scope_and_permission(self):
        self.ready()
        self.plan.approvers.add(self.scheduler)
        self.scheduler.user_permissions.add(
            Permission.objects.get(content_type__app_label="training", codename="approve_trainingplan")
        )
        self.scheduler = User.objects.get(pk=self.scheduler.pk)
        change = service.save_schedule(
            self.plan,
            self.scheduler,
            [self.change_slot(coaches=[self.collaborator.pk])],
            "本人申请并审批",
        )
        self.confirm_change_coaches(change)
        service.review_change(change, self.scheduler, approve=True)
        change.refresh_from_db()
        self.assertEqual(change.requested_by_id, change.reviewed_by_id)

    def test_started_execution_rechecked_at_approval(self):
        self.ready()
        task = self.new_task()
        service.publish_slot_task(task, self.coach)
        change = service.save_schedule(self.plan, self.scheduler, [self.change_slot(kind="general")], "改活动")
        execution = task.executions.get(user=self.student)
        update_execution_facts(execution, user=self.student, status="in_progress")
        with patch("django.utils.timezone.now", return_value=self.slot.ends_at):
            self.confirm_change_coaches(change)
            service.review_change(change, self.approver, approve=True)
        handoff = service.save_schedule(self.plan, self.scheduler, [self.change_slot(coaches=[self.collaborator.pk])], "结束前换教练")
        self.confirm_change_coaches(handoff)
        service.review_change(handoff, self.approver, approve=True)
        task.refresh_from_db()
        self.assertEqual(task.title, "部署服务")


    def test_cancel_unstarted_does_not_start_or_lock_and_started_cannot_remove(self):
        self.ready()
        task = self.new_task()
        service.publish_slot_task(task, self.coach)
        service.assign_competitors(task, self.coach, reason="调整名单", selected=[self.student.pk])
        removed = task.executions.get(user=self.student2)
        self.assertEqual(removed.status, "assigned")
        self.assertIsNotNone(removed.revoked_at)
        self.assertEqual(removed.revoke_reason, "调整名单")
        self.assertIsNone(removed.started_at)
        self.assertFalse(task.is_locked)
        service.assign_competitors(task, self.coach, reason="调整名单", selected=[self.student.pk, self.student2.pk])
        self.assertEqual(task.executions.count(), 2)
        started = task.executions.get(user=self.student)
        update_execution_facts(started, user=self.student, status="in_progress")
        with self.assertRaisesMessage(ValidationError, "已经开始"):
            service.assign_competitors(task, self.coach, reason="调整名单", selected=[self.student2.pk])
        service.save_slot_task(self.slot, self.coach, {"title": "结束前允许修改"}, task=task)

    def test_skill_correction_after_start_and_archive_keeps_history(self):
        self.ready()
        task = self.new_task()
        service.publish_slot_task(task, self.coach)
        update_execution_facts(task.executions.get(user=self.student), user=self.student, status="in_progress")
        self.plan.status = "archived"
        self.plan.save()
        skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="LDAP")
        service.set_task_skills(task, self.coach, [skill.pk])
        self.assertEqual(task.skill_links.get().skill_id, skill.pk)
        self.assertTrue(task.change_records.filter(action="修正技能关联").exists())
        service.save_slot_task(self.slot, self.coach, {"title": "改归档任务"}, task=task)
        task.refresh_from_db()
        self.assertEqual(task.title, "改归档任务")
        service.assign_competitors(task, self.coach, reason="调整名单", selected=[self.student.pk])
        self.assertEqual(task.executions.filter(revoked_at__isnull=True).count(), 1)

    def test_cancel_task_keeps_started_facts_and_blocks_updates(self):
        self.ready()
        task = self.new_task()
        service.publish_slot_task(task, self.coach)
        execution = task.executions.get(user=self.student)
        update_execution_facts(execution, user=self.student, status="in_progress")
        with self.assertRaisesMessage(ValidationError, "撤回"):
            service.cancel_task(task, self.coach, "调整任务")
        execution.refresh_from_db()
        self.assertIsNotNone(execution.started_at)
        self.assertEqual(task.executions.count(), 2)
        update_execution_facts(execution, user=self.student, status="completed")

    def test_audit_records_cannot_be_overwritten(self):
        record = service.audit(self.plan, self.admin, "测试记录")
        with self.assertRaises(ValidationError):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()

    def test_export_layout_and_only_published_effective_content(self):
        self.ready()
        first = self.new_task(title="第一任务" * 15)
        second = self.new_task(title="第二任务")
        draft = self.new_task(title="机密草稿")
        TrainingTask.objects.filter(pk=draft.pk).update(status="draft")
        service.publish_slot_task(first, self.coach)
        service.publish_slot_task(second, self.coach)
        rest = self.day.slots.get(period="evening")
        change = service.save_schedule(self.plan, self.scheduler, [self.change_slot(rest, kind="rest")], "晚间休息")
        self.confirm_change_coaches(change)
        service.review_change(change, self.approver, approve=True)
        service.save_schedule(
            self.plan, self.scheduler, [self.change_slot(coaches=[self.collaborator.pk])], "待审批改主教练"
        )
        sheet = load_workbook(BytesIO(build_plan_workbook(self.plan)))["训练计划"]
        self.assertEqual(
            [sheet.cell(2, col).value for col in range(1, 9)],
            ["日期", "星期", "时间", "领域", "训练任务", "负责教练", "值班教练", "备注"],
        )
        self.assertIn("第二任务", sheet["E4"].value)
        self.assertNotIn("机密草稿", str(list(sheet.values)))
        self.assertEqual(sheet["D6"].value, "休息")
        self.assertIn("A3:A6", str(sheet.merged_cells))
        self.assertIn("coach", sheet["F4"].value)
        self.assertNotIn("（主）", sheet["F4"].value)
        self.assertTrue(sheet["E4"].alignment.wrap_text)

    def test_export_preserves_formula_like_titles_and_notes_as_text(self):
        self.ready()
        self.plan.title = "=1+1"
        self.plan.save()
        self.day.note = "=HYPERLINK(\"https://example.invalid\")"
        self.day.save()
        sheet = load_workbook(BytesIO(build_plan_workbook(self.plan)))["训练计划"]
        self.assertEqual(sheet["A1"].data_type, "s")
        self.assertEqual(sheet["H3"].data_type, "s")
        self.assertEqual(sheet["A1"].font.name, "仿宋")
        self.assertEqual(sheet["A1"].font.sz, 18)

    def test_http_modal_title_only_and_foreign_candidate_denied(self):
        self.ready()
        self.client.force_login(self.coach)
        url = reverse("training:slot_task_create", args=[self.slot.pk])
        response = self.client.post(url, {"title": "只填标题"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "任务已保存；只有已发布任务对选手可见。")
        self.assertNotContains(response, "<html")
        self.assertEqual(response.headers["HX-Trigger"], "scheduleChanged")
        self.assertEqual(TrainingTask.objects.get(title="只填标题").assign_all, True)
        self.client.force_login(self.student)
        search = reverse("training:task_competitor_search", args=[self.slot.pk])
        self.assertEqual(self.client.get(search, {"q": "student"}).status_code, 403)
        self.assertEqual(self.client.post(url, {"title": "越权"}).status_code, 403)

    def test_htmx_saves_only_related_row_and_filter_changes_refresh_results(self):
        self.ready()
        self.client.force_login(self.coach)
        url = reverse("training:slot_task_create", args=[self.slot.pk])
        current = "http://testserver" + reverse("training:plan_detail", args=[self.plan.pk])
        response = self.client.post(url, {"title": "局部新增"}, HTTP_HX_REQUEST="true", HTTP_HX_CURRENT_URL=current)
        self.assertIn('"rowsUpdated": true', response.headers["HX-Trigger"])
        self.assertNotContains(response, "<html")
        self.assertContains(response, "局部新增")
        unrelated = self.day.slots.get(period="evening")
        self.assertNotContains(response, f'id="schedule-slot-{unrelated.pk}"')
        response = self.client.post(
            url, {"title": "筛选中新增"}, HTTP_HX_REQUEST="true", HTTP_HX_CURRENT_URL=current + "?q=LDAP"
        )
        self.assertEqual(response.headers["HX-Trigger"], "scheduleChanged")
        self.assertNotContains(response, 'hx-swap-oob="outerHTML"')

    def test_http_filter_and_private_execution_visibility(self):
        self.ready()
        task = self.new_task(title="LDAP训练")
        service.publish_slot_task(task, self.coach)
        self.client.force_login(self.student)
        response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]), {"q": "LDAP", "tab": "tasks"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["table"].data), 1)
        self.assertEqual(self.client.get(reverse("training:my_training")).status_code, 200)
        detail = self.client.get(reverse("training:task_detail", args=[task.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            list(detail.context["visible_executions"].values_list("user_id", flat=True)), [self.student.pk]
        )

    def test_plan_detail_task_filters_and_fragment(self):
        self.ready()
        task = self.new_task(title="LDAP训练")
        service.publish_slot_task(task, self.coach)
        self.client.force_login(self.scheduler)
        url = reverse("training:plan_detail", args=[self.plan.pk])
        schedule = self.client.get(url)
        self.assertContains(schedule, 'name="q"')
        self.assertNotContains(schedule, 'data-training-clear-selection')
        self.assertNotContains(schedule, '官方已到执行时间的任务分配')
        page = self.client.get(url, {"tab": "tasks"})
        self.assertContains(page, 'name="q"')
        self.assertEqual(
            {row.day.date for row in page.context["table"].data},
            set(self.plan.schedule_days.values_list("date", flat=True)),
        )
        self.assertContains(page, 'tab tab-active')
        self.assertContains(page, f'{url}?tab=details')
        response = self.client.get(url, {"tab": "tasks", "fragment": "results", "q": "LDAP"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "LDAP训练")
        self.assertNotContains(response, "<html")
        self.assertEqual(len(response.context["table"].data), 1)

    def test_all_assigned_coaches_can_fill_slot_tasks(self):
        self.ready()
        self.assertTrue(service.can_fill(self.collaborator, self.slot, create=True))
        self.slot.coaches.remove(self.collaborator)
        self.assertFalse(service.can_fill(self.collaborator, self.slot, create=True))

    def test_http_invalid_form_retains_inputs_and_cannot_spoof_selected_days(self):
        self.ready()
        self.client.force_login(self.scheduler)
        url = reverse("training:schedule_edit", args=[self.plan.pk])
        response = self.client.get(url, {"days": [self.day.pk], "day_only": "1"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "编辑全天排班")
        self.assertNotContains(response, "<html")
        response = self.client.post(
            url,
            {
                "days": [self.day.pk],
                "day_only": "1",
                "day-TOTAL_FORMS": 0,
                "day-INITIAL_FORMS": 0,
                "slot-TOTAL_FORMS": 0,
                "slot-INITIAL_FORMS": 0,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["day_forms"].non_form_errors())

    def test_http_schedule_save_uses_local_fragment_and_next_day(self):
        self.ready(publish=False)
        self.client.force_login(self.scheduler)
        url = reverse("training:schedule_edit", args=[self.plan.pk])
        response = self.client.get(url, {"days": self.day.pk, "day_only": "1"}, HTTP_HX_REQUEST="true")
        data = {"days": self.day.pk, "day_only": "1", "reason": "更新备注"}
        for key in ("day", "slot"):
            formset = response.context[f"{key}_forms"]
            data[f"{key}-TOTAL_FORMS"] = len(formset)
            data[f"{key}-INITIAL_FORMS"] = len(formset)
            for form in formset:
                for name, value in form.initial.items():
                    if name in form.fields and value is not None and value is not False:
                        data[f"{form.prefix}-{name}"] = "on" if value is True else value
        data["day-0-note"] = "测试备注保留"
        response = self.client.post(url, data, HTTP_HX_REQUEST="true")
        self.assertContains(response, "继续下一天")
        self.assertEqual(response.headers["HX-Trigger"], "scheduleChanged")
        self.assertNotContains(response, "<html")
        self.day.refresh_from_db()
        self.assertEqual(self.day.note, "测试备注保留")

    def test_snapshot_does_not_refresh_on_unrelated_day_edit(self):
        self.ready(all_coaches=True)
        original = set(self.day.duty_coaches.values_list("pk", flat=True))
        self.person("new-coach-after-publish", "coach")
        before = service.day_snapshot(self.day)
        payload = [
            {
                "type": "day",
                "id": self.day.pk,
                "revision": self.day.revision,
                "before": before,
                "after": before | {"note": "只改备注"},
            }
        ]
        change = service.save_schedule(self.plan, self.scheduler, payload, "修改备注")
        self.confirm_change_coaches(change)
        service.review_change(change, self.approver, approve=True)
        self.assertSetEqual(set(self.day.duty_coaches.values_list("pk", flat=True)), original)

    def test_title_only_edit_does_not_change_published_assignment_snapshot(self):
        self.ready()
        task = self.new_task()
        service.publish_slot_task(task, self.coach)
        later = self.person("new-student-after-publish", "competitor")
        self.client.force_login(self.coach)
        response = self.client.post(
            reverse("training:task_edit", args=[task.pk]), {"title": "仅修改标题"}, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.title, "仅修改标题")
        self.assertFalse(task.executions.filter(user=later).exists())

    def test_permission_only_cannot_export_task_titles(self):
        self.ready()
        self.student.user_permissions.remove(
            Permission.objects.get(content_type__app_label="training", codename="view_trainingtask")
        )
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("training:plan_export", args=[self.plan.pk])).status_code, 403)

    def test_admin_workflow_is_read_only_and_audit_bulk_updates_denied(self):
        from django.contrib import admin

        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:training_trainingplan_change", args=[self.plan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        record = service.audit(self.plan, self.admin, "测试审计不可覆盖")
        with self.assertRaises(ValidationError):
            self.plan.change_records.filter(pk=record.pk).update(action="覆盖")
        with self.assertRaises(ValidationError):
            self.plan.change_records.filter(pk=record.pk).delete()
        self.assertIn(TrainingScheduleSlot, admin.site._registry)

    def test_legacy_attach_keeps_ids_and_started_legacy_is_rejected(self):
        self.ready()
        legacy = TrainingTask.objects.create(
            training_plan=self.plan, planned_date=self.day.date, title="旧任务", created_by=self.admin
        )
        pk = legacy.pk
        service.attach_legacy_task(legacy, self.slot, self.admin)
        legacy.refresh_from_db()
        self.assertEqual(legacy.pk, pk)
        self.assertEqual(legacy.schedule_slot_id, self.slot.pk)
        historical = TrainingTask.objects.create(
            training_plan=self.plan, planned_date=self.day.date, title="历史执行", created_by=self.admin
        )
        TaskExecution.objects.create(training_task=historical, user=self.student, status="in_progress")
        with self.assertRaises(ValidationError):
            service.attach_legacy_task(historical, self.slot, self.admin)



    def test_entries_two_views_preserve_empty_and_disabled_slots(self):
        self.client.force_login(self.scheduler)
        url = reverse("training:plan_detail", args=[self.plan.pk])
        day = self.client.get(url)
        detail = self.client.get(url, {"tab": "details"})
        self.assertEqual(len(day.context["table"].data), 2)
        self.assertEqual(len(detail.context["table"].data), 8)
        self.assertContains(detail, "明细视图")
        self.assertContains(day, "data-week-toggle")
        self.assertContains(day, 'id="task-dialog"')

    def test_entries_both_views_paginate_by_dates_and_filter_slots(self):
        from datetime import timedelta
        type(self.cycle_obj).objects.filter(pk=self.cycle_obj.pk).update(end_date=self.plan.start_date + timedelta(days=40))
        self.cycle_obj.refresh_from_db()
        plan = TrainingPlan.objects.create(training_cycle=self.cycle_obj, title="长计划",
            start_date=self.plan.start_date, end_date=self.plan.start_date + timedelta(days=35), objective="训练", created_by=self.admin)
        service.initialize_schedule(plan)
        self.client.force_login(self.admin)
        url = reverse("training:plan_detail", args=[plan.pk])
        first = self.client.get(url, {"tab": "details"})
        self.assertEqual(len(first.context["table"].data), 124)
        second = self.client.get(url, {"tab": "details", "page": "2", "sort": "-date"})
        self.assertEqual(len(second.context["table"].data), 20)
        filtered = self.client.get(url, {"period": "morning", "date_from": plan.end_date.isoformat()})
        self.assertEqual(len(filtered.context["table"].data), 1)
        self.assertContains(filtered, "不符合筛选")
        invalid = self.client.get(url, {"domain": "invalid", "tab": "details"})
        self.assertEqual(len(invalid.context["table"].data), 0)






    def test_entries_withdraw_republish_preserves_assignments(self):
        from django.core import signing
        from .entry_operations import withdrawal_state, withdraw
        self.ready()
        task = self.new_task()
        ids = list(task.executions.values_list("pk", flat=True))
        _, guard = withdrawal_state(self.plan, self.admin, "task", task.pk)
        token = signing.dumps({"user": self.admin.pk, "plan": self.plan.pk, "level": "task", "task": task.pk,
            "reason": "修订", "guard": guard}, salt="training.withdraw")
        withdraw(self.plan, self.admin, token)
        task.refresh_from_db()
        self.assertEqual(task.status, "draft")
        service.publish_slot_task(task, self.coach)
        self.assertEqual(ids, list(task.executions.values_list("pk", flat=True)))
        _, guard = withdrawal_state(self.plan, self.admin, "task", task.pk)
        withdraw(self.plan, self.admin, signing.dumps({"user": self.admin.pk, "plan": self.plan.pk, "level": "task", "task": task.pk, "reason": "修订", "guard": guard}, salt="training.withdraw"))
        _, guard = withdrawal_state(self.plan, self.admin, "schedule")
        token = signing.dumps({"user": self.admin.pk, "plan": self.plan.pk, "level": "schedule",
            "reason": "修订", "guard": guard}, salt="training.withdraw")
        withdraw(self.plan, self.admin, token)
        self.plan.refresh_from_db()
        task.refresh_from_db()
        self.assertIsNone(self.plan.schedule_published_at)
        self.assertIsNotNone(self.plan.published_at)
        self.assertEqual(task.status, "draft")

    def test_entries_withdraw_forbidden_after_progress(self):
        from .entry_operations import withdrawal_state
        self.ready()
        task = self.new_task()
        execution = task.executions.get(user=self.student)
        from .models import TrainingProgress
        TrainingProgress.objects.create(execution=execution, author=self.student, completed="已学习")
        for user, level, task_id in [(self.admin, "plan", None), (self.admin, "schedule", None), (self.admin, "task", task.pk)]:
            with self.assertRaises(ValidationError):
                withdrawal_state(self.plan, user, level, task_id)


    def test_entries_single_domain_other_and_secondary_coach_form(self):
        from .schedule_forms import SlotScheduleForm
        form = SlotScheduleForm({"object_id": self.slot.pk, "revision": self.slot.revision,
            "period": "morning", "state": "scheduled", "domain_choice": "other",
            "coaches": [self.coach.pk, self.collaborator.pk]}, plan=self.plan, initial={"period": "morning"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["kind"], "general")
        self.assertFalse(form.cleaned_data["domains"].exists())
        self.assertIsNone(form.cleaned_data["primary_domain"])




    def test_entries_withdraw_plan_and_return_conditions(self):
        from .models import TrainingPlanParticipant
        from .entry_operations import withdrawal_state
        self.ready()
        task = self.new_task()
        from . import plan_clear
        state = plan_clear.state(self.plan, self.admin, "withdraw_tasks")
        plan_clear.execute(self.plan, self.admin, "withdraw_tasks", "修订", state["digest"])
        from django.core import signing
        from .entry_operations import withdraw
        _, guard = withdrawal_state(self.plan, self.admin, "schedule")
        withdraw(self.plan, self.admin, signing.dumps({"user": self.admin.pk, "plan": self.plan.pk, "level": "schedule", "reason": "修订", "guard": guard}, salt="training.withdraw"))
        self.plan.refresh_from_db()
        self.client.force_login(self.admin)
        url = reverse("training:withdraw_publication", args=[self.plan.pk, "plan"])
        response = self.client.post(url, {"reason": "修订", "return_query": "tab=details&period=morning&page=9&next=https://invalid.example"})
        self.assertTrue(response.context["token"])
        response = self.client.post(url, {"token": response.context["token"]})
        self.assertEqual(response.status_code, 302)
        self.assertIn("tab=details", response.url)
        self.assertNotIn("invalid.example", response.url)
        self.plan.refresh_from_db()
        self.assertIsNone(self.plan.published_at)
        self.assertIsNone(self.plan.schedule_published_at)
        task.refresh_from_db()
        self.assertEqual(task.status, "draft")
        later = self.person("late-member", "competitor")
        TrainingPlanParticipant.objects.create(training_plan=self.plan, user=later)
        self.plan.published_at = timezone.now()
        self.plan.save()
        self.plan.schedule_published_at = timezone.now()
        self.plan.save()
        service.publish_slot_task(task, self.coach)
        self.assertFalse(task.executions.filter(user=later).exists())

    def test_entries_task_expansion_and_editor_targets(self):
        self.ready()
        for title in ("第一项", "第二项", "第三项"):
            self.new_task(title=title)
        self.client.force_login(self.coach)
        url = reverse("training:plan_detail", args=[self.plan.pk])
        response = self.client.get(url)
        self.assertContains(response, "还有 1 项")
        self.assertContains(response, 'data-task-expand')
        self.assertContains(response, 'hx-target="#task-editor"')
        for title in ("第一项", "第二项", "第三项"):
            self.assertContains(response, title)
        editor = self.client.get(reverse("training:slot_task_create", args=[self.slot.pk]), HTTP_HX_REQUEST="true", HTTP_HX_TARGET="task-editor")
        self.assertContains(editor, 'hx-target="#task-editor"')
        self.assertNotContains(editor, '<html')
        self.client.force_login(self.scheduler)
        other = self.client.get(reverse("training:schedule_edit", args=[self.plan.pk]), {"days": self.day.pk, "slot": self.slot.pk}, HTTP_HX_REQUEST="true")
        self.assertNotContains(other, '>类型<')
        self.assertContains(other, 'name="slot-0-domain_choice"')
