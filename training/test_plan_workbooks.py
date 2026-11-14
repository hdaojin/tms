from io import BytesIO
from copy import copy
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from . import scheduling
from .plan_workbooks import TEMPLATE, build_plan_workbook, confirm_import, import_rosters, preview_import
from .test_process_refactor import ProcessFixture


class PlanWorkbookTests(ProcessFixture, TestCase):
    def test_import_uses_full_page_through_preview_and_confirmation(self):
        self.empty_plan()
        self.client.force_login(self.admin)
        url = reverse("training:plan_import", args=[self.plan.pk])
        detail_url = reverse("training:plan_detail", args=[self.plan.pk])
        detail = self.client.get(detail_url)
        self.assertContains(detail, f'href="{url}" aria-label="导入 Excel。预览并导入排班和任务草稿。">导入 Excel</a>', html=False)
        page = self.client.get(url)
        self.assertContains(page, f'href="{detail_url}">取消</a>', html=False)
        self.assertNotContains(page, 'hx-post=')
        upload = SimpleUploadedFile(
            "plan.xlsx", self.workbook().getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        preview = self.client.post(url, {"file": upload})
        self.assertContains(preview, "确认导入")
        self.assertContains(preview, "任务分配选手（2 人）")
        self.assertNotContains(preview, self.student.username)
        self.assertNotContains(preview, 'hx-post=')
        response = self.client.post(url, {"token": preview.context["token"]})
        self.assertRedirects(response, detail_url)

    def test_export_and_import_template_show_weekday_as_text(self):
        for import_template in (False, True):
            with self.subTest(import_template=import_template):
                sheet = load_workbook(
                    BytesIO(build_plan_workbook(self.plan, import_template=import_template))
                )["训练计划"]
                for row in (3, 7):
                    day = sheet.cell(row, 1).value
                    weekday = sheet.cell(row, 2)
                    self.assertEqual(weekday.value, "星期" + "一二三四五六日"[day.weekday()])
                    self.assertEqual(weekday.data_type, "s")

    def test_export_only_contains_viewers_assigned_task_content(self):
        self.task(title="只给选手一的保密任务", assign_all=False, competitors=[self.student.pk])
        self.task(slot=self.other_slot(), title="只给选手二的保密任务", assign_all=False, competitors=[self.student2.pk])
        first = load_workbook(BytesIO(build_plan_workbook(self.plan, self.student)))["训练计划"]
        second = load_workbook(BytesIO(build_plan_workbook(self.plan, self.student2)))["训练计划"]
        self.assertIn("只给选手一", first["E4"].value)
        self.assertNotIn("只给选手二", str(list(first.values)))
        self.assertIn("只给选手二", str(list(second.values)))
        self.assertNotIn("只给选手一", str(list(second.values)))

    def test_special_domains_import_and_export_with_distinct_labels(self):
        for entered, kind, exported in (
            ("综合", "comprehensive", "综合"),
            ("其他", "general", "其他"),
        ):
            with self.subTest(entered=entered):
                self.empty_plan()
                workbook = load_workbook(self.workbook(task=""))
                workbook["训练计划"]["D4"] = entered
                upload = BytesIO()
                workbook.save(upload)

                records, payload = preview_import(self.plan, self.admin, upload)
                self.assertEqual([record["status"] for record in records], ["成功"])
                confirm_import(self.plan, self.admin, payload, self.members())
                self.slot.refresh_from_db()
                self.assertEqual(self.slot.kind, kind)
                self.assertIsNone(self.slot.primary_domain_id)
                self.assertTrue(scheduling.slot_complete(self.slot))
                sheet = load_workbook(BytesIO(build_plan_workbook(self.plan)))["训练计划"]
                self.assertEqual(sheet["D4"].value, exported)

    def test_import_rejects_obsolete_special_domain_label(self):
        self.empty_plan()
        workbook = load_workbook(self.workbook(task=""))
        workbook["训练计划"]["D4"] = "综合活动"
        upload = BytesIO()
        workbook.save(upload)

        records, _ = preview_import(self.plan, self.admin, upload)
        self.assertEqual([record["status"] for record in records], ["错误"])
        self.assertIn("不存在或不属于该周期", records[0]["message"])

    def test_import_confirmation_rechecks_tasks_created_after_preview(self):
        self.empty_plan()
        _, payload = preview_import(self.plan, self.admin, self.workbook())
        from .models import TrainingTask
        TrainingTask.objects.create(training_plan=self.plan, schedule_slot=self.slot, planned_date=self.plan.start_date,
                                    title="预览后新增", created_by=self.admin)
        with self.assertRaisesMessage(ValidationError, "已有任务"):
            confirm_import(self.plan, self.admin, payload, self.members())
        self.assertEqual(self.plan.tasks.count(), 1)

    def empty_plan(self):
        self.plan.schedule_published_at = None
        self.plan.save(update_fields=["schedule_published_at", "updated_at"])
        for day in self.plan.schedule_days.all():
            day.duty_coaches.clear()
            day.duty_all, day.note = False, ""
            day.save()
            for slot in day.slots.all():
                slot.domains.clear()
                slot.coaches.clear()
                slot.primary_domain = None
                slot.coaches_all = False
                slot.kind = "pending" if slot.is_configured else "unused"
                slot.save()
        self.slot.refresh_from_db()

    def members(self):
        return list(self.plan.participants.filter(is_active=True).order_by("user_id").values_list("user_id", flat=True))

    def workbook(self, task="一个完整任务\n第二段说明"):
        workbook = load_workbook(BytesIO(build_plan_workbook(self.plan)))
        sheet = workbook["训练计划"]
        # 本测试只导入第一天上午，其他日期/时段留空。
        for merged in list(sheet.merged_cells.ranges):
            if merged.min_row >= 3:
                sheet.unmerge_cells(str(merged))
        for row in sheet.iter_rows(min_row=3):
            for cell in row:
                cell.value = None
        for col, value in enumerate(
            [self.plan.start_date, "星期四", "上午", self.linux.name, task, self.coach.username, "", ""], 1
        ):
            sheet.cell(4, col, value)
        stream = BytesIO()
        workbook.save(stream)
        stream.seek(0)
        return stream

    def test_export_preserves_original_styles_and_four_rows_per_day(self):
        before = TEMPLATE.read_bytes()
        template = load_workbook(TEMPLATE)["训练计划"]
        sheet = load_workbook(BytesIO(build_plan_workbook(self.plan)))["训练计划"]
        self.assertEqual(sheet.max_column, 8)
        self.assertEqual(sheet.max_row, 10)
        self.assertEqual([sheet.cell(row, 3).value for row in range(3, 7)], ["早读", "上午", "下午", "晚上"])
        self.assertIn("A3:A6", map(str, sheet.merged_cells.ranges))
        for col in range(1, 9):
            self.assertEqual(sheet.cell(2, col)._style, template.cell(2, col)._style)
            self.assertEqual(
                sheet.column_dimensions[chr(64 + col)].width, template.column_dimensions[chr(64 + col)].width
            )
        self.assertEqual(copy(sheet["E3"].font), copy(template["E3"].font))
        self.assertEqual(TEMPLATE.read_bytes(), before)
        self.assertEqual(load_workbook(BytesIO(build_plan_workbook(self.plan))).sheetnames, ["训练计划"])

    def test_one_cell_one_task_with_unpublished_schedule(self):
        self.empty_plan()
        self.plan.participants.update(was_initial=False)
        records, payload = preview_import(self.plan, self.admin, self.workbook())
        self.assertEqual([record["status"] for record in records], ["成功"])
        confirm_import(self.plan, self.admin, payload, self.members())
        task = self.plan.tasks.get()
        self.assertEqual(task.title, "一个完整任务")
        self.assertEqual(task.overview, "第二段说明")
        self.assertEqual(task.status, "draft")
        self.assertEqual(task.executions.count(), 0)
        self.assertEqual(task.selected_competitors.count(), 2)
        self.assertIsNone(self.plan.schedule_published_at)
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.primary_domain_id, self.linux.pk)
        with self.assertRaisesMessage(ValidationError, "已有任务"):
            preview_import(self.plan, self.admin, self.workbook())
        for day in self.plan.schedule_days.all():
            if day.pk == self.slot.day_id:
                day.duty_coaches.add(self.coach)
            for slot in day.slots.exclude(pk=self.slot.pk).filter(is_configured=True):
                slot.kind = "rest"
                slot.save()
        self.client.force_login(self.admin)
        publish_url = reverse("training:schedule_publish", args=[self.plan.pk])
        detail = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
        self.assertContains(detail, f'action="{publish_url}"', html=False)
        response = self.client.post(publish_url, follow=True)
        self.assertContains(response, "排班已发布")
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.schedule_published_at)
        task.refresh_from_db()
        self.assertEqual(task.status, "draft")
        self.plan.participants.filter(user=self.student).update(is_active=False)
        task.refresh_from_db()
        scheduling.publish_slot_task(task, self.coach)
        self.assertEqual(set(task.executions.values_list("user_id", flat=True)), {self.student.pk, self.student2.pk})

    def test_confirm_rechecks_whole_plan_and_preserves_all_data(self):
        self.empty_plan()
        records, payload = preview_import(self.plan, self.admin, self.workbook())
        day = self.plan.schedule_days.last()
        day.note = "预览后修改"
        day.save()
        with self.assertRaisesMessage(ValidationError, "已有值班或备注"):
            confirm_import(self.plan, self.admin, payload, self.members())
        self.assertEqual(self.plan.tasks.count(), 0)
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.kind, "pending")

    def test_invalid_row_blocks_all_and_weekday_warning(self):
        self.empty_plan()
        stream = self.workbook()
        workbook = load_workbook(stream)
        sheet = workbook["训练计划"]
        sheet["B4"] = "星期一"
        for col, value in enumerate(["错误日期", "", "下午", "不存在", "错误任务"], 1):
            sheet.cell(5, col, value)
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        records, payload = preview_import(self.plan, self.admin, output)
        self.assertEqual([record["status"] for record in records], ["警告", "错误"])
        self.assertEqual(payload, [])
        self.client.force_login(self.admin)
        response = self.client.post(reverse("training:plan_import", args=[self.plan.pk]), {
            "file": SimpleUploadedFile("plan.xlsx", output.getvalue(),
                                       content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        })
        self.assertFalse(response.context["token"])
        self.assertContains(response, "错误日期")

    def test_import_rolls_back_all_changes_on_failure(self):
        self.empty_plan()
        _, payload = preview_import(self.plan, self.admin, self.workbook())
        with patch("training.scheduling.save_slot_task", side_effect=ValidationError("失败")):
            with self.assertRaises(ValidationError):
                confirm_import(self.plan, self.admin, payload, self.members())
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.kind, "pending")
        self.assertFalse(self.plan.tasks.exists())

    def test_cancelled_task_history_does_not_prevent_import(self):
        self.empty_plan()
        from .models import TrainingTask
        old = TrainingTask.objects.create(training_plan=self.plan, schedule_slot=self.slot,
                                          planned_date=self.plan.start_date, title="历史任务",
                                          status="cancelled", created_by=self.admin)
        _, payload = preview_import(self.plan, self.admin, self.workbook())
        confirm_import(self.plan, self.admin, payload, self.members())
        old.refresh_from_db()
        self.assertEqual(old.status, "cancelled")
        self.assertEqual(self.plan.tasks.filter(status="draft").count(), 1)

    def test_scheduler_can_import_without_being_slot_coach(self):
        self.empty_plan()
        scheduler = self.person("other-scheduler", "coach")
        self.plan.schedulers.add(scheduler)
        _, payload = preview_import(self.plan, scheduler, self.workbook())
        confirm_import(self.plan, scheduler, payload, self.members())
        self.assertEqual(self.plan.tasks.count(), 1)
        with self.assertRaises(PermissionDenied):
            preview_import(self.plan, self.student, self.workbook())

    def test_warning_allows_import_but_empty_snapshot_blocks_task(self):
        self.empty_plan()
        workbook = load_workbook(self.workbook())
        workbook["训练计划"]["B4"] = "星期一"
        output = BytesIO()
        workbook.save(output)
        records, payload = preview_import(self.plan, self.admin, BytesIO(output.getvalue()))
        self.assertEqual(records[0]["status"], "警告")
        self.assertTrue(payload)
        self.plan.participants.update(is_active=False)
        records, payload = preview_import(self.plan, self.admin, BytesIO(output.getvalue()))
        self.assertEqual(records[0]["status"], "错误")
        self.assertIn("当前参与选手", records[0]["message"])
        self.assertFalse(payload)

    def test_confirm_rechecks_duty_roster_changes(self):
        self.empty_plan()
        rosters = import_rosters(self.plan)
        _, payload = preview_import(self.plan, self.admin, self.workbook())
        self.plan.duty_personnel.add(self.student)
        with self.assertRaisesMessage(ValidationError, "值班人员已经变化"):
            confirm_import(self.plan, self.admin, payload, self.members(), rosters)
        self.assertFalse(self.plan.tasks.exists())

    def test_confirm_rechecks_initial_competitors_and_permission(self):
        self.empty_plan()
        scheduler = self.person("changing-scheduler", "coach")
        self.plan.schedulers.add(scheduler)
        _, payload = preview_import(self.plan, scheduler, self.workbook())
        members = self.members()
        self.plan.participants.filter(user=self.student).update(is_active=False)
        with self.assertRaisesMessage(ValidationError, "参与选手已经变化"):
            confirm_import(self.plan, scheduler, payload, members)
        self.plan.participants.filter(user=self.student).update(is_active=True)
        from django.contrib.auth.models import Permission
        scheduler.user_permissions.remove(Permission.objects.get(content_type__app_label="training", codename="add_trainingtask"))
        scheduler = type(scheduler).objects.get(pk=scheduler.pk)
        with self.assertRaises(PermissionDenied):
            confirm_import(self.plan, scheduler, payload, members)
        self.assertFalse(self.plan.tasks.exists())
