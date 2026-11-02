from io import BytesIO
from copy import copy
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from openpyxl import load_workbook

from . import scheduling
from .plan_workbooks import TEMPLATE, build_plan_workbook, preview_import
from .test_process_refactor import ProcessFixture


class PlanWorkbookTests(ProcessFixture, TestCase):
    def test_export_only_contains_viewers_assigned_task_content(self):
        self.task(title="只给选手一的保密任务", assign_all=False, competitors=[self.student.pk])
        self.task(title="只给选手二的保密任务", assign_all=False, competitors=[self.student2.pk])
        first = load_workbook(BytesIO(build_plan_workbook(self.plan, self.student)))["训练计划"]
        second = load_workbook(BytesIO(build_plan_workbook(self.plan, self.student2)))["训练计划"]
        self.assertIn("只给选手一", first["E4"].value)
        self.assertNotIn("只给选手二", str(list(first.values)))
        self.assertIn("只给选手二", second["E4"].value)
        self.assertNotIn("只给选手一", str(list(second.values)))

    def test_import_confirmation_rechecks_tasks_created_after_preview(self):
        _, payload = preview_import(self.plan, self.admin, self.workbook())
        self.task(title="预览后新增")
        with self.assertRaisesMessage(ValidationError, "已有任务"):
            scheduling.save_schedule(self.plan, self.admin, payload, "过时预览")
        self.assertEqual(self.plan.tasks.count(), 1)

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

    def test_partial_import_one_cell_one_task_and_approval(self):
        records, payload = preview_import(self.plan, self.admin, self.workbook())
        self.assertEqual([record["status"] for record in records], ["成功"])
        request = scheduling.save_schedule(self.plan, self.admin, payload, "导入任务")
        self.assertEqual(self.plan.tasks.count(), 0)
        self.confirm_change_coaches(request)
        scheduling.review_change(request, self.admin, approve=True)
        task = self.plan.tasks.get()
        self.assertEqual(task.description, "一个完整任务\n第二段说明")
        self.assertEqual(task.status, "draft")
        self.assertEqual(task.executions.count(), 0)
        scheduling.publish_slot_task(task, self.coach)
        self.assertEqual(task.executions.count(), 2)
        records, payload = preview_import(self.plan, self.admin, self.workbook())
        self.assertEqual(records[0]["status"], "错误")
        self.assertEqual(payload, [])

    def test_confirm_rechecks_lock_and_preserves_all_data(self):
        records, payload = preview_import(self.plan, self.admin, self.workbook())
        with patch("django.utils.timezone.now", return_value=self.slot.ends_at):
            request = scheduling.save_schedule(self.plan, self.admin, payload, "逾时导入，补记实际安排")
            self.assertEqual(request.confirmations, [])
        self.assertEqual(self.plan.tasks.count(), 0)
        self.assertEqual(self.plan.schedule_changes.count(), 1)

    def test_invalid_row_does_not_remove_valid_rows_and_weekday_warning(self):
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
        self.assertEqual(len(payload), 1)
