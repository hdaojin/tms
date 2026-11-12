import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch

from accounts.services.users import get_user_display_name

from .checklists import completion_counts
from .daily_progress import active_executions, has_text, scheduled_tasks, validate_training_day
from .models import TrainingCycleMember, TrainingProgress

COACH = TrainingCycleMember.Role.COACH
STUDENT = TrainingCycleMember.Role.COMPETITOR
COMMON_FIELDS = (
    ("achievement", "训练目标达成情况"),
    ("shortcomings", "不足之处"),
)
FIELDS = {
    COACH: (("process", "过程记录"), *COMMON_FIELDS, ("improvement", "改进方向")),
    STUDENT: (("notes", "学习笔记"), *COMMON_FIELDS, ("improvement", "改进建议")),
}
FIELD_LIMIT = 8000


def progress_material(record):
    if record.checklist is not None:
        return {
            "已完成": [item["title"] for item in record.checklist if item["done"]],
            "未完成": [item["title"] for item in record.checklist if not item["done"]],
            "存在问题": record.problems.strip(),
        }
    return {"完成内容": record.completed.strip(), "存在问题": record.problems.strip()}


def collect_sources(user, cycle, day):
    member = validate_training_day(user, cycle, day)
    required = ("training.view_taskexecution", "training.view_trainingprogress")
    if not user.has_perms(required):
        raise PermissionDenied
    executions = active_executions()
    tasks = scheduled_tasks(cycle, day)
    if member.role == COACH:
        tasks = tasks.filter(schedule_slot__coaches=user)
    else:
        executions = executions.filter(user=user)
        tasks = tasks.filter(pk__in=executions.values("training_task_id"))
    executions = executions.prefetch_related(
        Prefetch("progress_records", TrainingProgress.objects.filter(training_date=day), to_attr="daily_records"),
    ).order_by("pk")
    tasks = (
        tasks.select_related("training_plan", "schedule_slot")
        .prefetch_related(
            "schedule_slot__domains",
            "schedule_slot__coaches",
            Prefetch("executions", executions, to_attr="daily_executions"),
        )
        .order_by("training_plan_id", "schedule_slot__starts_at", "order", "pk")
    )

    entries, materials, missing, teachers = [], [], [], {}
    goal_task_ids = []
    for task in tasks:
        slot = task.schedule_slot
        outline = [item["title"] for item in task.subtasks]
        domains = [domain.name for domain in slot.domains.all()]
        entry = {
            "id": task.pk,
            "title": task.title,
            "plan": task.training_plan.title,
            "plan_id": task.training_plan_id,
            "period": slot.get_period_display(),
            "domains": domains if slot.period != "early" else [],
            "goal": task.requirements.strip(),
            "outline": outline,
            "execution_ids": [execution.pk for execution in task.daily_executions],
        }
        records = [
            record
            for execution in task.daily_executions
            for record in execution.daily_records
            if record.checklist is not None or has_text(record)
        ]
        progress = [progress_material(record) for record in records]
        counts = [count for record in records if (count := completion_counts(record)) is not None]
        if counts and member.role == STUDENT:
            entry["completion"] = list(counts[0])
        if counts and member.role == COACH:
            entry["fully_completed"] = sum(done == total for done, total in counts)
            entry["has_completion_counts"] = True
        slot_teachers = {teacher.pk: get_user_display_name(teacher) for teacher in slot.coaches.all()}
        teachers.update(slot_teachers)
        entry["filled"], entry["expected"] = len(progress), len(task.daily_executions)
        entry["version"] = hashlib.sha256(
            json.dumps(
                [entry, progress, sorted(slot_teachers.items()) if member.role == STUDENT else []],
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        material = {
            "训练计划": entry["plan"],
            "任务": entry["title"],
            "时段": entry["period"],
            "训练模块": domains,
            "子任务": outline,
            "训练目标": entry["goal"],
            "执行填报": progress,
        }
        if member.role == COACH:
            material.update({"训练目标": entry["goal"], "已填人数": entry["filled"], "应填人数": entry["expected"]})
            if not entry["goal"]:
                goal_task_ids.append(str(task.pk))
                material["任务编号"] = str(task.pk)
        elif not progress:
            missing.append("当天尚未填完训练完成情况，请先完成填报。")
        entries.append(entry)
        materials.append(material)

    if not entries:
        missing.append("所选训练日没有符合条件的官方任务。")
    project = cycle.skill_project.name
    header = {
        "heading": f"第{cycle.log_edition}届世界技能大赛{project.removesuffix('项目')}项目{cycle.log_class}",
        "author": get_user_display_name(user),
        "date": day.isoformat(),
        "role": member.role,
        "teachers": "、".join(dict.fromkeys(teachers.values())) if member.role == STUDENT else "",
    }
    source = {"format": 2, "header": header, "tasks": entries}
    if goal_task_ids:
        source["goal_task_ids"] = goal_task_ids
    return source, materials, list(dict.fromkeys(missing))


def check_source_access(old, current):
    if not old or old["header"]["role"] != current["header"]["role"]:
        raise ValidationError("草稿缺少有效训练素材，请重新生成。")
    allowed = {entry["id"]: set(entry["execution_ids"]) for entry in current["tasks"]}
    for task in old["tasks"]:
        if task["id"] not in allowed or not set(task["execution_ids"]).issubset(allowed[task["id"]]):
            raise ValidationError("部分任务或选手执行记录已不在可用范围，请按当前素材重新生成。")


def changed_sources(old, current):
    previous = {task["id"]: task for task in old.get("tasks", [])}
    new = {task["id"]: task for task in current["tasks"]}
    changed = [
        f"{task['plan']} · {task['period']} · {task['title']}"
        for pk, task in (previous | new).items()
        if previous.get(pk, {}).get("version") != new.get(pk, {}).get("version")
    ]
    if old.get("header") != current["header"]:
        changed.append("训练周期、授课老师或填写人信息")
    return changed


def validate_body(role, body, source=None):
    fields = dict(FIELDS[role])
    current_format = bool(source and source.get("format") == 2)
    needs_title = current_format and len(source["tasks"]) > 1
    needs_content = current_format and any(not task["outline"] for task in source["tasks"])
    goal_task_ids = set(source.get("goal_task_ids", ())) if current_format and role == COACH else set()
    expected = set(fields)
    if needs_title:
        expected.add("task_title")
    if needs_content:
        expected.add("suggested_items")
    if goal_task_ids:
        expected.add("suggested_goals")
    if (
        not isinstance(body, dict)
        or body.keys() != expected
        or any(
            not isinstance(body[key], str) or not body[key].strip() or len(body[key]) > FIELD_LIMIT for key in fields
        )
    ):
        raise ValidationError("日志正文栏目缺失、为空或超过长度限制，请检查后重试。")
    result = {key: body[key].strip() for key in fields}
    if needs_title:
        title = body["task_title"]
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 20 or "\n" in title or "\r" in title:
            raise ValidationError("训练任务概括标题须为一行且最多 20 字。")
        result["task_title"] = title.strip()
    if needs_content:
        items = body["suggested_items"]
        if (
            not isinstance(items, list)
            or not 1 <= len(items) <= 10
            or any(not isinstance(item, str) or not item.strip() or len(item) > 240 for item in items)
        ):
            raise ValidationError("补充训练内容须为 1 至 10 条，每条最多 240 字。")
        result["suggested_items"] = [item.strip() for item in items]
    if goal_task_ids:
        goals = body["suggested_goals"]
        if (
            not isinstance(goals, dict)
            or goals.keys() != goal_task_ids
            or any(not isinstance(goal, str) or not goal.strip() or len(goal) > 400 for goal in goals.values())
        ):
            raise ValidationError("请为每项缺少训练目标的任务提供有效目标，每项最多 400 字。")
        result["suggested_goals"] = {key: goal.strip() for key, goal in goals.items()}
    return result
