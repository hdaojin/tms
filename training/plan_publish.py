"""整份计划任务的发布预览和原子确认。"""

import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.services.users import get_user_display_name
from . import entry_operations, scheduling
from .models import TaskExecution, TrainingPlan, TrainingScheduleDay, TrainingScheduleSlot, TrainingTask


@transaction.atomic
def preview(plan, user):
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    if not scheduling.can_schedule(user, plan) or not user.has_perm("training.change_trainingtask"):
        raise PermissionDenied
    if not plan.published_at or not plan.schedule_published_at:
        raise ValidationError("请先发布训练计划和整份排班。")
    tasks = list(plan.tasks.filter(status="draft").select_related("schedule_slot__day").order_by("planned_date", "order", "pk"))
    if not tasks:
        raise ValidationError("没有待发布的任务草稿。")
    slot_ids = list(TrainingScheduleSlot.objects.filter(day__training_plan=plan).values_list("pk", flat=True))
    day_ids = list(plan.schedule_days.values_list("pk", flat=True))
    guard = {
        "fingerprint": entry_operations.fingerprint(plan, slot_ids, day_ids),
        "tasks": [(task.pk, task.status, task.updated_at.isoformat(), task.schedule_slot_id,
                   scheduling.task_snapshot(task)) for task in tasks],
        "members": list(plan.participants.order_by("user_id").values_list("user_id", "is_active")),
    }
    rows = []
    for task in tasks:
        row = {"task": task, "people": [], "error": ""}
        if not task.schedule_slot_id:
            row["error"] = "历史任务没有所属时段，无法发布。"
        else:
            try:
                with transaction.atomic():
                    published = scheduling.publish_slot_task(task, user)
                    executions = published.executions.filter(revoked_at__isnull=True).exclude(status="cancelled").select_related("user").order_by("user_id")
                    row["people"] = [(entry.user_id, get_user_display_name(entry.user)) for entry in executions]
                    transaction.set_rollback(True)
            except PermissionDenied:
                row["error"] = "时段未完成排班或没有权限发布该任务。"
            except ValidationError as exc:
                row["error"] = "；".join(exc.messages)
        rows.append(row)
    guard["results"] = [(row["task"].pk, row["people"], row["error"]) for row in rows]
    digest = hashlib.sha256(json.dumps(guard, sort_keys=True, default=str).encode()).hexdigest()
    return {"rows": rows, "digest": digest, "can_confirm": not any(row["error"] for row in rows)}


@transaction.atomic
def publish(plan, user, digest):
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    list(TrainingScheduleDay.objects.select_for_update().filter(training_plan=plan))
    list(TrainingScheduleSlot.objects.select_for_update().filter(day__training_plan=plan))
    list(TrainingTask.objects.select_for_update().filter(training_plan=plan))
    list(TaskExecution.objects.select_for_update().filter(training_task__training_plan=plan))
    result = preview(plan, user)
    if result["digest"] != digest:
        raise ValidationError("任务、排班或选手名单已经变化，请重新预览。")
    if not result["can_confirm"]:
        raise ValidationError("存在无法发布的任务，请处理后重新预览。")
    for row in result["rows"]:
        scheduling.publish_slot_task(row["task"], user)
