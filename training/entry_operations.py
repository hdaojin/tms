"""固定目标的批量编排、复制与撤回；预览内容签名后重新校验。"""

import hashlib
import json
from datetime import timedelta

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from . import scheduling as service
from .models import TaskExecution, TrainingPlan, TrainingScheduleSlot, TrainingTask


def execution_facts(tasks):
    return (
        TaskExecution.objects.filter(training_task__in=tasks)
        .filter(
            Q(started_at__isnull=False)
            | ~Q(status__in=["assigned", "cancelled"])
            | Q(progress_records__isnull=False)
            | Q(state_changes__isnull=False)
            | ~Q(coach_feedback="")
            | Q(feedback_records__isnull=False)
            | Q(attachments__isnull=False)
            | Q(training_logs__isnull=False)
            | Q(completed_at__isnull=False)
            | Q(actual_minutes__isnull=False)
            | ~Q(completion_note="")
            | ~Q(problems="")
            | ~Q(solution="")
            | ~Q(reflection="")
        )
    )


def has_execution_facts(tasks):
    return execution_facts(tasks).exists()


def fingerprint(plan, slot_ids, day_ids):
    slots = (
        TrainingScheduleSlot.objects.filter(pk__in=slot_ids, day__training_plan=plan)
        .prefetch_related("coaches", "domains")
        .order_by("pk")
    )
    days = plan.schedule_days.filter(pk__in=day_ids).prefetch_related("duty_coaches").order_by("pk")
    tasks = (
        TrainingTask.objects.filter(Q(schedule_slot__in=slots) | Q(schedule_slot__day__in=days))
        .prefetch_related("skill_links", "selected_competitors")
        .order_by("pk")
    )
    data = {
        "publication": [str(plan.published_at), str(plan.schedule_published_at), plan.status],
        "slots": [
            (
                slot.pk,
                slot.revision,
                slot.is_configured,
                str(slot.starts_at),
                str(slot.ends_at),
                service.slot_snapshot(slot),
            )
            for slot in slots
        ],
        "days": [(day.pk, day.revision, service.day_snapshot(day)) for day in days],
        "tasks": [(task.pk, str(task.updated_at), service.task_snapshot(task)) for task in tasks],
        "executions": list(
            TaskExecution.objects.filter(training_task__in=tasks)
            .order_by("pk")
            .values_list("pk", "status", "started_at", "revoked_at", "updated_at")
        ),
        "facts": has_execution_facts(tasks),
    }
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()


def check_guard(plan, guard):
    # 调用者持有计划锁；同时锁执行记录，防止确认/终审期间开始执行。
    list(
        TaskExecution.objects.select_for_update(of=("self",)).filter(
            Q(training_task__schedule_slot_id__in=guard["slots"])
            | Q(training_task__schedule_slot__day_id__in=guard["days"])
        )
    )
    if fingerprint(plan, guard["slots"], guard["days"]) != guard["fingerprint"]:
        raise ValidationError("来源、目标或发布状态已经变化，请重新预览。")


def serial_values(cleaned):
    return {
        key: ([obj.pk for obj in value] if hasattr(value, "model") else value.pk if hasattr(value, "pk") else value)
        for key, value in cleaned.items()
    }


def approval_required(plan, payload, operation, reason):
    from .change_workflow import payload_expired

    required = payload_expired(plan, payload) or (operation != "tasks" and bool(plan.schedule_published_at))
    if required and not reason.strip():
        raise ValidationError("已发布或过期修改须填写调整原因和实际执行情况。")
    return required


@transaction.atomic
def preview(plan, user, command):
    raise ValidationError("本版本暂不开放批量编排和快捷调班。")
    # 排班写入统一锁计划，使差异和来源指纹来自同一份现状。
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    operation = command["operation"]
    if operation not in {"schedule", "copy", "tasks", "clear", "unused", "swap"}:
        raise ValidationError("无效的批量操作。")
    if operation == "tasks":
        if not user.has_perm("training.add_trainingtask"):
            raise PermissionDenied
    elif not service.can_schedule(user, plan):
        raise PermissionDenied
    if operation == "swap":
        return preview_swap(plan, user, command)
    days = list(plan.schedule_days.order_by("date"))
    day_ids = set(command.get("days", []))
    explicit = set(command.get("slots", []))
    periods = command.get("periods", [])
    slots = list(
        TrainingScheduleSlot.objects.filter(day__training_plan=plan)
        .select_related("day__training_plan")
        .order_by("day__date", "pk")
    )
    by_id = {slot.pk: slot for slot in slots}
    for slot in slots:
        slot.day.training_plan = plan
    if not explicit.issubset(by_id) or not day_ids.issubset({day.pk for day in days}):
        raise PermissionDenied
    if not periods or not set(periods).issubset(TrainingScheduleSlot.Period.values):
        raise ValidationError("请选择有效时段。")
    start, end = command.get("date_from"), command.get("date_to")
    if start and end and start > end:
        raise ValidationError("开始日期不能晚于结束日期。")
    if not day_ids and not explicit and not start and not end:
        raise ValidationError("请选择目标日期或日期范围。")
    targets = [
        slot
        for slot in slots
        if (
            slot.pk in explicit
            if explicit
            else slot.day_id in day_ids
            if day_ids
            else (not start or slot.day.date.isoformat() >= start) and (not end or slot.day.date.isoformat() <= end)
        )
        and slot.period in periods
        and (not command.get("weekdays") or str(slot.day.date.weekday()) in command["weekdays"])
    ]
    if not targets:
        raise ValidationError("没有匹配的目标时段。")
    source = plan.schedule_days.filter(pk=command.get("source")).first() if command.get("source") else None
    if command.get("source") and source is None:
        raise PermissionDenied
    source_map = {(slot.day.date, slot.period): slot for slot in slots}
    payload, skipped, rows, affected_sources, affected_days = [], [], [], set(), set()
    if start and start < plan.start_date.isoformat():
        skipped.append(f"早于计划开始日期 {plan.start_date} 的目标日期已跳过")
    if end and end > plan.end_date.isoformat():
        skipped.append(f"晚于计划结束日期 {plan.end_date} 的目标日期已跳过")
    for slot in targets:
        label = f"{slot.day.date} {slot.get_period_display()}"
        if not slot.is_configured:
            skipped.append(f"{label}：未启用")
            continue
        before = service.slot_snapshot(slot)
        if operation == "tasks":
            if not service.can_fill(user, slot, create=True):
                raise PermissionDenied
            service.validate_slot(plan, dict(before), publishing=True)
            for title in command["titles"]:
                values = {
                    "title": title,
                    "description": command.get("description", ""),
                    "skills": [],
                    "assign_all": True,
                    "competitors": [],
                }
                payload.append(
                    {
                        "type": "task",
                        "id": None,
                        "slot": slot.pk,
                        "revision": slot.revision,
                        "before": {},
                        "updated_at": None,
                        "after": values,
                        "publish": False,
                    }
                )
            rows.append(
                {"label": label, "before": "保留已有任务", "after": f"追加 {len(command['titles'])} 项任务草稿"}
            )
            continue
        if operation in {"clear", "unused"}:
            after = before | {
                "kind": "pending" if operation == "clear" else "unused",
                "domains": [],
                "primary_domain": None,
                "coaches_all": False,
                "coaches": [],
            }
        elif operation == "copy":
            mode = command.get("copy_mode", "day")
            source_date = (
                slot.day.date - timedelta(days=7)
                if mode == "previous"
                else source.date + timedelta(days=slot.day.date.weekday() - source.date.weekday())
                if mode == "week"
                else source.date
            )
            origin = source_map.get((source_date, slot.period))
            if not origin or not origin.is_configured:
                skipped.append(f"{label}：来源越界或未启用")
                continue
            if origin.pk == slot.pk:
                skipped.append(f"{label}：与来源相同")
                continue
            affected_sources.add(origin.pk)
            after = service.slot_snapshot(origin) | {"period": slot.period}
            if command.get("include_duty") or command.get("include_note"):
                affected_days.update([origin.day_id, slot.day_id])
                day_before = service.day_snapshot(slot.day)
                day_after = dict(day_before)
                source_day = service.day_snapshot(origin.day)
                for key in (["duty_all", "duty_coaches"] if command.get("include_duty") else []) + (
                    ["note"] if command.get("include_note") else []
                ):
                    day_after[key] = source_day[key]
                # 日级信息与时段采用同一覆盖策略，在确定时段写入后加入。
        else:
            after = before | command["schedule"]
        occupied = slot.kind != "pending" or bool(before["coaches"] or before["domains"]) or slot.tasks.exists()
        if operation in {"copy", "schedule"} and occupied and not command.get("overwrite"):
            skipped.append(f"{label}：已有安排，未选择覆盖")
            continue
        if has_execution_facts(slot.tasks.all()):
            raise ValidationError(f"{label}：已有执行事实，不能覆盖或清空。")
        if operation in {"clear", "unused"} and slot.tasks.exclude(status="cancelled").exists():
            raise ValidationError(f"{label}：请先处理该时段的任务。")
        service.validate_slot(plan, after, publishing=bool(plan.schedule_published_at) and after["kind"] != "pending")
        for task in slot.tasks.exclude(status="cancelled"):
            service.validate_skills(task, list(task.skill_links.values_list("skill_id", flat=True)), after["domains"])
        day_changed = (
            operation == "copy"
            and (command.get("include_duty") or command.get("include_note"))
            and day_before != day_after
        )
        if before == after and not day_changed:
            skipped.append(f"{label}：内容未变化")
            continue
        if before != after:
            payload.append({"type": "slot", "id": slot.pk, "revision": slot.revision, "before": before, "after": after})
            rows.append({"label": label, "before": before, "after": after})
        if day_changed:
            if not any(item["type"] == "day" and item["id"] == slot.day_id for item in payload):
                payload.append(
                    {
                        "type": "day",
                        "id": slot.day_id,
                        "revision": slot.day.revision,
                        "before": day_before,
                        "after": day_after,
                    }
                )
                rows.append({"label": f"{slot.day.date} 值班 / 日备注", "before": day_before, "after": day_after})
    if not payload:
        raise ValidationError("没有可执行的变更。" + "；".join(skipped[:10]))
    ids = sorted({slot.pk for slot in targets} | affected_sources)
    guard = {"slots": ids, "days": sorted(affected_days), "fingerprint": fingerprint(plan, ids, affected_days)}
    payload[0]["entry_guard"] = guard
    needs_approval = approval_required(plan, payload, operation, command.get("reason", ""))
    return {
        "payload": payload,
        "rows": rows,
        "skipped": skipped,
        "guard": guard,
        "operation": operation,
        "approval_required": needs_approval,
        "reason": command.get("reason", ""),
        "user": user.pk,
        "plan": plan.pk,
        "return_query": command.get("return_query", ""),
    }


@transaction.atomic
def confirm(plan, user, token):
    raise ValidationError("本版本暂不开放批量编排和快捷调班。")
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    data = signing.loads(token, salt="training.entries", max_age=600)
    if data["user"] != user.pk or data["plan"] != plan.pk:
        raise PermissionDenied
    check_guard(plan, data["guard"])
    payload = data["payload"]
    if data["operation"] == "tasks":
        for item in payload:
            slot = TrainingScheduleSlot.objects.select_related("day__training_plan").get(pk=item["slot"])
            if not service.can_fill(user, slot, create=True):
                raise PermissionDenied
        from .change_workflow import create_change, payload_expired, apply_payload

        if payload_expired(plan, payload):
            return create_change(plan, user, payload, data["reason"])
        apply_payload(plan, payload, user)
        service.audit(plan, user, "批量追加任务", after={"调整": payload})
        return None
    if data["operation"] == "swap":
        if not service.can_schedule(user, plan):
            raise PermissionDenied
        from .change_workflow import create_change, payload_expired, apply_payload

        if plan.schedule_published_at or payload_expired(plan, payload):
            return create_change(plan, user, payload, data["reason"])
        apply_payload(plan, payload, user)
        service.audit(plan, user, "快捷交换排班", after={"调整": payload})
        return None
    return service.save_schedule(plan, user, payload, data["reason"])


def preview_swap(plan, user, command):
    from .change_workflow import swap_snapshot
    from .selectors import visible_training_tasks_for

    day_ids = [command.get("first"), command.get("second")]
    days = {day.pk: day for day in plan.schedule_days.filter(pk__in=day_ids)}
    periods = command.get("periods", [])
    if (
        len(days) != 2
        or day_ids[0] == day_ids[1]
        or not periods
        or not set(periods).issubset(TrainingScheduleSlot.Period.values)
    ):
        raise ValidationError("请选择两个不同日期和有效时段。")
    payload, rows, ids = [], [], []
    for period in periods:
        left, right = (
            TrainingScheduleSlot.objects.select_related("day__training_plan").get(day_id=pk, period=period)
            for pk in day_ids
        )
        if not left.is_configured or not right.is_configured:
            raise ValidationError("未启用的时段不能交换。")
        ids.extend([left.pk, right.pk])
        payload.append(
            {"type": "swap", "slots": [left.pk, right.pk], "before": [swap_snapshot(left), swap_snapshot(right)]}
        )
        first = service.slot_snapshot(left) | {
            "可见任务": list(
                visible_training_tasks_for(user).filter(schedule_slot=left).values_list("title", flat=True)
            )
        }
        second = service.slot_snapshot(right) | {
            "可见任务": list(
                visible_training_tasks_for(user).filter(schedule_slot=right).values_list("title", flat=True)
            )
        }
        rows.append(
            {
                "label": f"{left.day.date} ↔ {right.day.date} {left.get_period_display()}",
                "before": {str(left.day.date): first, str(right.day.date): second},
                "after": {str(left.day.date): second, str(right.day.date): first},
            }
        )
    for day_id, other_id in (day_ids, day_ids[::-1]):
        before, origin = service.day_snapshot(days[day_id]), service.day_snapshot(days[other_id])
        after = before | {
            key: origin[key]
            for key in (["duty_all", "duty_coaches"] if command.get("include_duty") else [])
            + (["note"] if command.get("include_note") else [])
        }
        if before != after:
            payload.append(
                {"type": "day", "id": day_id, "revision": days[day_id].revision, "before": before, "after": after}
            )
            rows.append({"label": f"{days[day_id].date} 值班 / 日备注", "before": before, "after": after})
    guard = {"slots": ids, "days": sorted(day_ids), "fingerprint": fingerprint(plan, ids, day_ids)}
    payload[0]["entry_guard"] = guard
    needs_approval = approval_required(plan, payload, "swap", command.get("reason", ""))
    return {
        "payload": payload,
        "rows": rows,
        "skipped": [],
        "guard": guard,
        "operation": "swap",
        "approval_required": needs_approval,
        "reason": command.get("reason", ""),
        "user": user.pk,
        "plan": plan.pk,
        "return_query": command.get("return_query", ""),
    }


def withdrawal_state(plan, user, level, task_id=None, *, preview=True):
    task = plan.tasks.select_related("schedule_slot__day__training_plan").get(pk=task_id) if level == "task" else None
    if not service.privileged(user) or level not in {"task", "schedule", "plan"}:
        raise PermissionDenied
    if level == "plan" and (plan.schedule_published_at or plan.tasks.filter(status="published").exists()):
        raise ValidationError("请先撤回全部任务和排班发布。")
    if level == "schedule" and plan.tasks.filter(status="published").exists():
        raise ValidationError("请先撤回全部任务发布。")
    if not (
        task.status == "published" if task else plan.published_at if level == "plan" else plan.schedule_published_at
    ):
        raise ValidationError("该内容尚未发布或已撤回。")
    tasks = plan.tasks.filter(pk=task.pk) if task else plan.tasks.all()
    if has_execution_facts(tasks):
        raise ValidationError("受影响任务已有执行或进度，不能撤回发布。")
    if not preview:
        return
    ids = list(tasks.exclude(schedule_slot=None).values_list("schedule_slot_id", flat=True))
    return task, {"slots": ids, "days": [], "fingerprint": fingerprint(plan, ids, [])}


@transaction.atomic
def withdraw(plan, user, token):
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    data = signing.loads(token, salt="training.withdraw", max_age=600)
    if data["user"] != user.pk or data["plan"] != plan.pk:
        raise PermissionDenied
    list(TaskExecution.objects.select_for_update().filter(training_task__training_plan=plan))
    task, guard = withdrawal_state(plan, user, data["level"], data.get("task"))
    if guard != data["guard"]:
        raise ValidationError("内容已经变化，请重新预览撤回。")
    if task:
        before = service.task_snapshot(task)
        task.status = "draft"
        task.save(update_fields=["status", "updated_at"])
    else:
        before = service.plan_snapshot(plan)
        field = "published_at" if data["level"] == "plan" else "schedule_published_at"
        setattr(plan, field, None)
        if data["level"] == "plan":
            plan.status = "draft"
        plan.save(update_fields=[field, "status", "updated_at"])
    service.audit(
        plan, user, "撤回发布", before=before, after={"层级": data["level"]}, reason=data["reason"], task=task
    )
