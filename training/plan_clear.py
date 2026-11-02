"""整份训练计划的任务撤回和两阶段清空。"""

import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from . import entry_operations, scheduling
from .models import TaskExecution, TrainingPlan, TrainingScheduleDay, TrainingScheduleSlot, TrainingTask


def state(plan, user, action):
    if action not in {"withdraw_tasks", "clear_tasks", "clear_schedule"}:
        raise PermissionDenied
    if action == "withdraw_tasks":
        if not scheduling.privileged(user):
            raise PermissionDenied
    elif not scheduling.can_schedule(user, plan):
        raise PermissionDenied
    tasks = list(plan.tasks.exclude(status="cancelled").select_related("schedule_slot__day").order_by("pk"))
    if action == "clear_tasks" and not user.has_perm("training.change_trainingtask"):
        raise PermissionDenied
    if action == "withdraw_tasks":
        targets = [task for task in tasks if task.status == "published"]
        if not targets:
            raise ValidationError("没有已发布的任务。")
        facts = entry_operations.execution_facts(TrainingTask.objects.filter(pk__in=[task.pk for task in targets]))
        blocked_ids = set(facts.values_list("training_task_id", flat=True))
        if blocked_ids:
            blocked = [str(task) for task in targets if task.pk in blocked_ids]
            raise ValidationError("以下任务存在执行或进度事实，不能撤回：" + "；".join(blocked))
    elif action == "clear_tasks":
        targets = tasks
        if not targets:
            raise ValidationError("没有需要清空的任务。")
        if any(task.status == "published" for task in tasks):
            raise ValidationError("请先撤回以下任务发布：" + "；".join(str(task) for task in tasks if task.status == "published"))
        facts = entry_operations.execution_facts(TrainingTask.objects.filter(pk__in=[task.pk for task in targets]))
        blocked_ids = set(facts.values_list("training_task_id", flat=True))
        if blocked_ids:
            blocked = [str(task) for task in targets if task.pk in blocked_ids]
            raise ValidationError("以下任务存在执行或进度事实，不能清空：" + "；".join(blocked))
    else:
        targets = []
        if tasks:
            raise ValidationError("请先清空全部任务。")
        if plan.schedule_published_at:
            raise ValidationError("请先撤回排班发布。")
        if entry_operations.has_execution_facts(plan.tasks.all()):
            raise ValidationError("计划中存在任务执行或进度事实，不能清空排班。")
    days = list(plan.schedule_days.prefetch_related("duty_coaches").order_by("date"))
    slots = list(TrainingScheduleSlot.objects.filter(day__training_plan=plan).select_related("day").prefetch_related("domains", "coaches").order_by("day__date", "pk"))
    slot_ids = [slot.pk for slot in slots]
    day_ids = [day.pk for day in days]
    guard = {
        "fingerprint": entry_operations.fingerprint(plan, slot_ids, day_ids),
        "tasks": [(task.pk, task.status, task.updated_at.isoformat(), task.schedule_slot_id) for task in tasks],
        "facts": entry_operations.has_execution_facts(plan.tasks.all()),
    }
    digest = hashlib.sha256(json.dumps(guard, sort_keys=True).encode()).hexdigest()
    return {"targets": targets, "days": days, "slots": slots, "digest": digest}


@transaction.atomic
def execute(plan, user, action, reason, digest):
    if not reason.strip():
        raise ValidationError("请填写操作原因。")
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    list(TrainingScheduleDay.objects.select_for_update().filter(training_plan=plan))
    list(TrainingScheduleSlot.objects.select_for_update().filter(day__training_plan=plan))
    list(TrainingTask.objects.select_for_update().filter(training_plan=plan))
    list(TaskExecution.objects.select_for_update().filter(training_task__training_plan=plan))
    current = state(plan, user, action)
    if current["digest"] != digest:
        raise ValidationError("内容或发布状态已变化，请重新预览。")
    if action == "withdraw_tasks":
        for task in current["targets"]:
            before = scheduling.task_snapshot(task)
            task.status = "draft"
            task.save(update_fields=["status", "updated_at"])
            scheduling.audit(plan, user, "撤回任务发布", task=task, before=before, after=scheduling.task_snapshot(task), reason=reason)
    elif action == "clear_tasks":
        for task in current["targets"]:
            before = scheduling.task_snapshot(task)
            task.status = "cancelled"
            task.cancelled_at, task.cancelled_by, task.cancel_reason = timezone.now(), user, reason
            task.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancel_reason", "updated_at"])
            for execution in task.executions.filter(status="assigned", started_at__isnull=True):
                execution.revoked_at, execution.revoked_by, execution.revoke_reason = timezone.now(), user, reason
                execution.save(update_fields=["revoked_at", "revoked_by", "revoke_reason", "updated_at"])
            scheduling.audit(plan, user, "清空任务", task=task, before=before, after=scheduling.task_snapshot(task), reason=reason)
    else:
        changes = []
        for day in current["days"]:
            before = scheduling.day_snapshot(day)
            if day.duty_all or day.note or before["duty_coaches"]:
                day.duty_all, day.note = False, ""
                day.revision += 1
                day.save(update_fields=["duty_all", "note", "revision", "updated_at"])
                day.duty_coaches.clear()
                changes.append({"type": "day", "id": day.pk, "before": before, "after": scheduling.day_snapshot(day)})
        for slot in current["slots"]:
            before = scheduling.slot_snapshot(slot)
            kind = "pending" if slot.is_configured else "unused"
            if slot.kind != kind or slot.primary_domain_id or slot.coaches_all or before["domains"] or before["coaches"]:
                slot.kind, slot.primary_domain_id, slot.coaches_all = kind, None, False
                slot.revision += 1
                slot.save(update_fields=["kind", "primary_domain", "coaches_all", "revision", "updated_at"])
                slot.domains.clear()
                slot.coaches.clear()
                changes.append({"type": "slot", "id": slot.pk, "before": before, "after": scheduling.slot_snapshot(slot)})
        if not changes:
            raise ValidationError("排班已经清空。")
        scheduling.audit(plan, user, "清空全部排班", before={"调整": changes}, reason=reason)
