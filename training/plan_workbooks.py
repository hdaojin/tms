"""原八列计划模板的复制导出与只读导入预览。"""

from copy import copy, deepcopy
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel

from accounts.services.users import get_user_display_name
from . import scheduling
from .models import TrainingPlan, TrainingScheduleDay, TrainingScheduleSlot, TrainingTask

TEMPLATE = Path(__file__).parent / "resources" / "templates" / "training_plan.xlsx"
HEADERS = ["日期", "星期", "时间", "领域", "训练任务", "负责教练", "值班教练", "备注"]
PERIODS = dict((label, value) for value, label in TrainingScheduleSlot.Period.choices)
ROUNDTRIP_NOTICE = "同一时段多个独立任务导出为单元格内换行；再次导入时整个单元格会成为一个任务，不按换行拆分。"


def build_plan_workbook(plan, user=None, *, import_template=False):
    workbook = load_workbook(TEMPLATE)
    for name in list(workbook.sheetnames):
        if name != "训练计划":
            del workbook[name]
    sheet = workbook["训练计划"]
    styles = {row: [copy(sheet.cell(row, col)._style) for col in range(1, 9)] for row in (3, 4, 5)}
    heights = {row: sheet.row_dimensions[row].height for row in (3, 4, 5)}
    for merged in list(sheet.merged_cells.ranges):
        if merged.min_row >= 3:
            sheet.unmerge_cells(str(merged))
    sheet.delete_rows(3, sheet.max_row)
    for row in list(sheet.row_dimensions):
        if row >= 3:
            del sheet.row_dimensions[row]
    # 原文件在 H 列以后只有空白格式，不作为业务列导出。
    if sheet.max_column > 8:
        sheet.delete_cols(9, sheet.max_column - 8)
    for key in list(sheet.column_dimensions):
        from openpyxl.utils.cell import column_index_from_string

        if column_index_from_string(key) > 8:
            del sheet.column_dimensions[key]
    sheet["A1"] = plan.title
    sheet["A1"].data_type = "s"
    from django.db.models import Prefetch
    from .models import TrainingTask
    from .selectors import visible_training_tasks_for

    tasks = TrainingTask.objects.none() if import_template else TrainingTask.objects.all() if user is None else visible_training_tasks_for(user)
    days = plan.schedule_days.prefetch_related(
        "duty_coaches", "slots__coaches", "slots__domains", Prefetch("slots__tasks", queryset=tasks)
    ).order_by("date")
    row = 3
    for day in days:
        slots = {slot.period: slot for slot in day.slots.all()}
        periods = [
            (period, label) for period, label in TrainingScheduleSlot.Period.choices
            if import_template or (slots.get(period) and slots[period].is_configured)
        ]
        for offset, (period, label) in enumerate(periods):
            slot = slots.get(period)
            style_row = {"early": 3, "morning": 3, "afternoon": 4, "evening": 5}[period]
            sheet.row_dimensions[row + offset].height = heights[style_row]
            for col, style in enumerate(styles[style_row], 1):
                sheet.cell(row + offset, col)._style = copy(style)
            tasks = (
                sorted(
                    (task for task in slot.tasks.all() if task.status == "published"),
                    key=lambda task: (task.order, task.pk),
                )
                if slot and not import_template
                else []
            )
            task_text = "\n".join(task.title + ("\n" + task.description if task.description else "") for task in tasks)
            coaches = (
                "全体"
                if slot and slot.coaches_all and not import_template
                else "\n".join(
                    get_user_display_name(user)
                    for user in slot.coaches.all()
                )
                if slot and not import_template
                else ""
            )
            duty = "" if import_template else ("全体" if day.duty_all else "\n".join(get_user_display_name(user) for user in day.duty_coaches.all()))
            values = [
                day.date,
                "星期" + "一二三四五六日"[day.date.weekday()],
                label,
                ("、".join(domain.name for domain in slot.domains.all()) or slot.get_kind_display()) if slot and not import_template else "",
                task_text,
                coaches,
                duty,
                "" if import_template else day.note,
            ]
            for col, value in enumerate(values, 1):
                cell = sheet.cell(row + offset, col, value)
                if isinstance(value, str):
                    cell.data_type = "s"
            sheet.row_dimensions[row + offset].height = max(
                heights[style_row] or 30, 18 * max(len(task_text.splitlines()), len(coaches.splitlines()), 1)
            )
        if len(periods) > 1:
            for col in (1, 2, 7, 8):
                sheet.merge_cells(start_row=row, end_row=row + len(periods) - 1, start_column=col, end_column=col)
        row += len(periods)
    if import_template:
        instructions = workbook.create_sheet("填写说明", 0)
        instructions["A1"] = "训练计划导入说明"
        instructions["A2"] = "模板每天保留四个时段。未设置的时段请将领域、训练任务和负责教练留空。"
        instructions["A3"] = "日期、星期、时段及表头保持不变；值班教练和备注按日期填写。"
        instructions.column_dimensions["A"].width = 100
        from openpyxl.comments import Comment
        for day_index, day in enumerate(days):
            for offset, (period, _) in enumerate(TrainingScheduleSlot.Period.choices):
                slot = next((item for item in day.slots.all() if item.period == period), None)
                if slot and not slot.is_configured:
                    sheet.cell(3 + day_index * 4 + offset, 3).comment = Comment("该时段未设置，领域、训练任务和负责教练须留空。", "TMS")
    sheet.print_area = f"A1:H{row - 1}"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _person_ids(text, coaches, *, require_primary=True):
    labels = [line.strip() for line in str(text).splitlines() if line.strip()]
    if "全体" in labels:
        if labels != ["全体"]:
            raise ValidationError("全体必须独占负责教练或值班教练单元格。")
        return True, [], None
    ids = []
    for label in labels:
        name = label.removesuffix("（主）").removesuffix("(主)").strip()
        matches = [user.pk for user in coaches if get_user_display_name(user) == name or user.username == name]
        if len(matches) != 1:
            raise ValidationError(f"教练“{name}”不存在、重名或不属于本周期。")
        if matches[0] in ids:
            raise ValidationError("教练名单重复。")
        ids.append(matches[0])
    return False, sorted(ids), None


def check_empty_plan(plan, user):
    if not scheduling.can_schedule(user, plan) or not user.has_perm("training.add_trainingtask"):
        raise PermissionDenied
    if not plan.published_at:
        raise ValidationError("请先发布计划，再导入排班。")
    if plan.schedule_published_at:
        raise ValidationError("仅能导入排班尚未发布的空计划。")
    if plan.tasks.exclude(status="cancelled").exists():
        raise ValidationError("计划已有任务，请先清空全部任务。")
    if plan.schedule_days.filter(duty_all=True).exists() or plan.schedule_days.exclude(note="").exists() or plan.schedule_days.filter(duty_coaches__isnull=False).exists():
        raise ValidationError("计划已有值班或备注，请先清空全部排班。")
    slots = TrainingScheduleSlot.objects.filter(day__training_plan=plan)
    if (slots.filter(is_configured=True).exclude(kind="pending").exists()
        or slots.filter(is_configured=False).exclude(kind="unused").exists()
        or slots.filter(primary_domain__isnull=False).exists()
        or slots.filter(coaches_all=True).exists()
        or slots.filter(domains__isnull=False).exists()
        or slots.filter(coaches__isnull=False).exists()):
        raise ValidationError("计划已有排班，请先清空全部排班。")


@transaction.atomic
def confirm_import(plan, user, payload, members):
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    list(TrainingScheduleDay.objects.select_for_update().filter(training_plan=plan))
    list(TrainingScheduleSlot.objects.select_for_update().filter(day__training_plan=plan))
    list(TrainingTask.objects.select_for_update().filter(training_plan=plan))
    check_empty_plan(plan, user)
    current_members = list(plan.participants.filter(is_active=True).order_by("user_id").values_list("user_id", flat=True))
    if members != current_members:
        raise ValidationError("计划参与选手已经变化，请重新预览。")
    if not payload:
        raise ValidationError("没有可导入的内容。")
    scheduling._apply_changes(plan, payload, user, approved=True, draft_import=True)
    scheduling.audit(plan, user, "导入排班和任务草稿", after={"调整": payload})


def preview_import(plan, user, file):
    check_empty_plan(plan, user)
    try:
        workbook = load_workbook(file, data_only=False)
    except Exception as exc:
        raise ValidationError("无法读取 Excel 工作簿，请使用原 xlsx 模板。") from exc
    if "训练计划" not in workbook.sheetnames:
        raise ValidationError("缺少训练计划工作表。")
    sheet = workbook["训练计划"]
    if [str(sheet.cell(2, col).value or "").strip() for col in range(1, 9)] != HEADERS:
        raise ValidationError("表头必须保持原模板八列及顺序。")
    if sheet.max_row > 10000:
        raise ValidationError("训练计划表数据行数过多。")
    merged = {}
    for area in sheet.merged_cells.ranges:
        if area.min_col == area.max_col and area.min_col in {1, 2, 7, 8}:
            for row in range(area.min_row, area.max_row + 1):
                merged[row, area.min_col] = sheet.cell(area.min_row, area.min_col)
    coaches = list(plan.training_cycle.members.filter(role="coach").select_related("user"))
    coaches = [member.user for member in coaches]
    domains = list(plan.training_cycle.skill_tree_version_links.select_related("technical_domain"))
    slots = {
        (slot.day.date, slot.period): slot
        for slot in TrainingScheduleSlot.objects.filter(day__training_plan=plan)
        .select_related("day__training_plan")
        .prefetch_related("coaches", "domains", "tasks")
    }
    records, changes, seen = [], {}, set()
    for row in range(3, sheet.max_row + 1):
        cells = [merged.get((row, col), sheet.cell(row, col)) for col in range(1, 9)]
        values = [cell.value for cell in cells]
        if not any(value is not None and str(value).strip() for value in values):
            continue
        entry = {"row": row, "status": "成功", "message": "", "warnings": [], "values": values}
        try:
            if any(cell.data_type == "f" for cell in cells):
                raise ValidationError("导入单元格不能包含公式。")
            when = values[0]
            if isinstance(when, datetime):
                when = when.date()
            elif isinstance(when, (int, float)):
                when = from_excel(when, workbook.epoch).date()
            elif not isinstance(when, date):
                when = date.fromisoformat(str(when).strip())
            period = PERIODS.get(str(values[2] or "").strip())
            slot = slots.get((when, period))
            if not slot:
                raise ValidationError("日期或时段无法识别，或不在目标计划内。")
            if (when, period) in seen:
                raise ValidationError("日期时段重复，不能覆盖同一时段。")
            weekday = values[1]
            if isinstance(weekday, (int, float)):
                weekday = from_excel(weekday, workbook.epoch)
            expected = "一二三四五六日"[when.weekday()]
            if weekday and (
                (isinstance(weekday, (date, datetime)) and weekday.weekday() != when.weekday())
                or (
                    isinstance(weekday, str)
                    and weekday.strip().removeprefix("星期").removeprefix("周")
                    not in {expected, "天" if expected == "日" else expected}
                )
            ):
                entry["warnings"].append("星期与日期不一致，以日期计算为准。")
            before = scheduling.slot_snapshot(slot)
            after = deepcopy(before)
            domain_text, task_text, coach_text, duty_text, note = [
                str(value).strip() if value is not None else "" for value in values[3:8]
            ]
            if not slot.is_configured and (domain_text or task_text or coach_text):
                raise ValidationError("该时段未设置，领域、训练任务和负责教练须留空。")
            if domain_text:
                if domain_text in {"休息", "不安排", "待排班", "综合", "综合活动"}:
                    after["kind"] = {
                        "休息": "rest",
                        "不安排": "unused",
                        "待排班": "pending",
                        "综合": "general",
                        "综合活动": "general",
                    }[domain_text]
                else:
                    matches = [
                        link.technical_domain.pk
                        for link in domains
                        if domain_text in {link.technical_domain.code, link.technical_domain.name}
                    ]
                    if len(matches) != 1:
                        raise ValidationError(f"训练领域“{domain_text}”不存在或不属于该周期。")
                    after.update(kind="technical", domains=matches, primary_domain=matches[0])
            if coach_text:
                all_coaches, ids, primary = _person_ids(coach_text, coaches)
                after.update(coaches_all=all_coaches, coaches=ids)
            for field in ("domains", "coaches", "primary_domain"):
                if before[field] and before[field] != after[field]:
                    raise ValidationError("目标时段已有冲突排班，不允许覆盖。")
            if before["kind"] not in {"pending", "unused"} and before["kind"] != after["kind"]:
                raise ValidationError("目标时段已有冲突类型，不允许覆盖。")
            if task_text and slot.tasks.exclude(status="cancelled").exists():
                raise ValidationError("目标时段已有任务，不允许覆盖或重复导入。")
            if task_text:
                if after["kind"] not in scheduling.ACTIVE_KINDS:
                    if task_text == "休息" and after["kind"] == "rest":
                        task_text = ""
                    else:
                        raise ValidationError("导入任务需要有效训练领域或综合活动排班。")
                if task_text and (
                    not user.has_perm("training.add_trainingtask")
                ):
                    raise ValidationError("无权编制该时段任务。")
                if task_text and not plan.participants.filter(is_active=True).exists():
                    raise ValidationError("计划没有当前参与选手，请先通过计划详情页的“编辑成员”添加选手。")
            if slot.is_configured:
                scheduling.validate_slot(plan, after, publishing=bool(task_text))
            candidate = dict(changes)
            if slot.is_configured:
                candidate["slot", slot.pk] = {
                    "type": "slot",
                    "id": slot.pk,
                    "revision": slot.revision,
                    "before": before,
                    "after": after,
                    "import_task": task_text,
                }
            day = slot.day
            day_before = scheduling.day_snapshot(day)
            day_change = deepcopy(
                candidate.get(
                    ("day", day.pk),
                    {
                        "type": "day",
                        "id": day.pk,
                        "revision": day.revision,
                        "before": day_before,
                        "after": deepcopy(day_before),
                    },
                )
            )
            if duty_text:
                duty_all, duty_ids, _ = _person_ids(duty_text, coaches, require_primary=False)
                if day_change["after"]["duty_coaches"] and day_change["after"]["duty_coaches"] != duty_ids:
                    raise ValidationError("同一日期的导入值班教练相互冲突。")
                if day_before["duty_coaches"] and day_before["duty_coaches"] != duty_ids:
                    raise ValidationError("目标日期已有冲突值班教练。")
                day_change["after"].update(duty_all=duty_all, duty_coaches=duty_ids)
            if note:
                if day_change["after"]["note"] and day_change["after"]["note"] != note:
                    raise ValidationError("同一日期的导入备注相互冲突。")
                if day_before["note"] and day_before["note"] != note:
                    raise ValidationError("目标日期已有冲突备注。")
                day_change["after"]["note"] = note
            if day_change["before"] != day_change["after"]:
                candidate["day", day.pk] = day_change
            changes = candidate
            seen.add((when, period))
            if before == after and not task_text and day_change["before"] == day_change["after"]:
                entry.update(status="跳过", message="无有效新增内容。")
            elif entry["warnings"]:
                entry["status"] = "警告"
        except (ValidationError, ValueError, TypeError, AttributeError) as exc:
            entry.update(
                status="错误",
                message="；".join(exc.messages) if isinstance(exc, ValidationError) else "日期或单元格格式不正确。",
            )
        records.append(entry)
    payload = [
        change for change in changes.values() if change["before"] != change["after"] or change.get("import_task")
    ]
    if any(record["status"] == "错误" for record in records):
        payload = []
    return records, payload
