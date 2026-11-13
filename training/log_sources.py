import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch

from accounts.services.users import get_user_display_name

from .checklists import completion_counts
from .daily_progress import active_executions, has_text, scheduled_tasks, validate_training_day
from .log_task_references import task_references
from .models import TrainingCycleMember, TrainingLog, TrainingProgress

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


def coach_references(cycle, day, task_coaches):
    coach_ids = set().union(*task_coaches.values())
    logs = TrainingLog.objects.filter(
        training_cycle=cycle,
        training_date=day,
        author_id__in=cycle.members.filter(role=COACH, user_id__in=coach_ids).values("user_id"),
    ).exclude(online_document={}).order_by("pk")
    snapshots, materials = [], []
    for log in logs:
        document = log.online_document
        if not isinstance(document, dict):
            continue
        body, source = document.get("body"), document.get("source")
        if not isinstance(body, dict) or not isinstance(body.get("process"), str) or not body["process"].strip():
            continue
        if not isinstance(source, dict) or not isinstance(source.get("header"), dict):
            continue
        if source["header"].get("role") != COACH or not isinstance(source.get("tasks"), list):
            continue
        excerpts = []
        for task in source["tasks"]:
            if not isinstance(task, dict) or not isinstance(task.get("id"), int):
                continue
            task_id = task["id"]
            excerpt = task.get("technical_excerpt")
            if log.author_id not in task_coaches.get(task_id, ()) or not isinstance(excerpt, dict):
                continue
            text_fields = ("任务", "训练说明", "训练目标")
            outline = excerpt.get("子任务")
            if not all(isinstance(excerpt.get(key), str) for key in text_fields):
                continue
            if not isinstance(outline, list) or not all(isinstance(title, str) for title in outline):
                continue
            excerpts.append({"任务编号": task_id, **{key: excerpt[key] for key in text_fields}, "子任务": outline})
        if not excerpts:
            continue
        snapshots.append({
            "id": log.pk,
            "cycle_id": cycle.pk,
            "date": day.isoformat(),
            "author_id": log.author_id,
            "task_ids": sorted(excerpt["任务编号"] for excerpt in excerpts),
            "version": hashlib.sha256(
                json.dumps([body["process"], source["tasks"], excerpts], ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest(),
        })
        materials.extend(excerpts)
    return snapshots, materials


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

    tasks = list(tasks)
    attachments = task_references(user, tasks)
    entries, materials, missing, teachers = [], [], [], {}
    task_coaches = {}
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
        task_coaches[task.pk] = set(slot_teachers)
        overview = task.overview.strip()
        files = attachments.get(task.pk, [])
        entry["has_overview"] = bool(overview)
        entry["reference_files"] = {str(pk): digest for pk, digest, _, _ in files}
        if member.role == COACH and (overview or entry["goal"] or outline):
            entry["technical_excerpt"] = {
                "任务": entry["title"],
                "训练说明": overview[:4000],
                "训练目标": entry["goal"][:1000],
                "子任务": [title[:240] for title in outline[:20]],
            }
        entry["filled"], entry["expected"] = len(progress), len(task.daily_executions)
        entry["version"] = hashlib.sha256(
            json.dumps(
                [entry, overview, progress, sorted(slot_teachers.items()) if member.role == STUDENT else []],
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
            "训练说明": overview[:8000],
            "任务附件": [{"文件": name, "摘录": excerpt} for _, _, name, excerpt in files],
            "执行填报": progress,
        }
        if member.role == COACH:
            material.update({"训练目标": entry["goal"], "已填人数": entry["filled"], "应填人数": entry["expected"]})
            if not entry["goal"]:
                goal_task_ids.append(str(task.pk))
                material["任务编号"] = str(task.pk)
        entries.append(entry)
        materials.append(material)

    if not entries:
        missing.append("所选训练日没有符合条件的官方任务。")
    audiences = "、".join(dict.fromkeys(task.training_plan.implementation_audience for task in tasks))
    header = {
        "heading": f"{cycle.name}{cycle.skill_project.name}{audiences}",
        "author": get_user_display_name(user),
        "date": day.isoformat(),
        "role": member.role,
        "teachers": "、".join(dict.fromkeys(teachers.values())) if member.role == STUDENT else "",
    }
    source = {"format": 2, "header": header, "tasks": entries}
    if goal_task_ids:
        source["goal_task_ids"] = goal_task_ids
    if member.role == STUDENT and task_coaches:
        source["coach_logs"], excerpts = coach_references(cycle, day, task_coaches)
        if excerpts:
            materials.append({"教练日志技术参考": excerpts})
    return source, materials, list(dict.fromkeys(missing))


def check_source_access(old, current):
    if not old or old["header"]["role"] != current["header"]["role"]:
        raise ValidationError("草稿缺少有效训练素材，请重新生成。")
    allowed = {entry["id"]: set(entry["execution_ids"]) for entry in current["tasks"]}
    for task in old["tasks"]:
        if task["id"] not in allowed or not set(task["execution_ids"]).issubset(allowed[task["id"]]):
            raise ValidationError("部分任务或选手执行记录已不在可用范围，请按当前素材重新生成。")
    current_tasks = {task["id"]: task for task in current["tasks"]}
    if any(
        not task.get("reference_files", {}).keys() <= current_tasks[task["id"]].get("reference_files", {}).keys()
        for task in old["tasks"]
    ):
        raise ValidationError("部分任务附件已不在可用范围，请按当前素材重新生成。")
    allowed_logs = {log["id"]: set(log["task_ids"]) for log in current.get("coach_logs", [])}
    if any(
        not set(log["task_ids"]).issubset(allowed_logs.get(log["id"], ())) for log in old.get("coach_logs", [])
    ):
        raise ValidationError("部分教练日志已不在可用范围，请按当前素材重新生成。")


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
    if old.get("coach_logs", []) != current.get("coach_logs", []):
        changed.append("教练日志技术参考")
    return changed


INLINE_DOCUMENT_FORMAT = 3


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
    if source and source.get("document_format") == INLINE_DOCUMENT_FORMAT:
        validate_inline_images(role, result, source["inline_image_ids"])
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


def validate_inline_images(role, body, image_ids):
    from bs4 import BeautifulSoup

    from core.documents.content import MARKDOWN_EXTRAS
    from core.utils.markdown import render_markdown_text

    image_field = "process" if role == COACH else "notes"
    allowed = {f"tms-asset:image-{pk}" for pk in image_ids}
    for key, value in body.items():
        html = render_markdown_text(value, extensions=MARKDOWN_EXTRAS, strict=True).html
        for image in BeautifulSoup(html, "html.parser").find_all("img"):
            src = image.get("src")
            if key != image_field or src not in allowed:
                raise ValidationError("插图须在过程记录或学习笔记中引用本次发送的图片，每张图片只能引用一次。")
            allowed.remove(src)
