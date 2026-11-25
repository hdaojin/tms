"""排班和任务调整的线下沟通确认、教练确认及终审。"""

from copy import deepcopy
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.permissions.registry import get_users_with_explicit_permission

from . import scheduling as service
from .models import TrainingPlan, TrainingScheduleChange, TrainingScheduleSlot, TrainingTask


def payload_expired(plan, payload):
    # 多时段和多任务共用一次时间边界查询，避免逐项查询相同时段。
    direct, scheduled, days = set(), set(), set()
    for item in payload:
        kind = item["type"]
        if kind == "swap":
            direct.update(item["slots"])
        elif kind == "task":
            direct.add(item["slot"])
        elif kind == "times":
            if item.get("include_past"):
                return True
        elif kind == "day":
            days.add(item["id"])
        else:
            scheduled.add(item["id"])
    if not (direct or scheduled or days):
        return False
    scope = Q(pk__in=direct) | (Q(is_configured=True) & (Q(pk__in=scheduled) | Q(day_id__in=days)))
    return TrainingScheduleSlot.objects.filter(day__training_plan=plan).filter(scope).filter(
        Q(ends_at__isnull=True) | Q(ends_at__lte=timezone.now())
    ).exists()


def apply_payload(plan, payload, actor):
    from .entry_operations import check_guard
    for item in payload:
        if item.get("entry_guard"):
            check_guard(plan, item["entry_guard"])
    schedule = [item for item in payload if item["type"] in {"day", "slot"}]
    result = None
    for item in payload:
        if item["type"] == "swap":
            apply_swap(plan, item)
        elif item["type"] == "times":
            raise ValidationError("旧时段时间调整申请已停止生效，可驳回后按当前规则编辑计划。")
        elif item["type"] == "task":
            slot = TrainingScheduleSlot.objects.select_related("day__training_plan").get(pk=item["slot"], day__training_plan=plan)
            if slot.revision != item["revision"]:
                raise ValidationError("排班已经变化，请重新申请任务修改。")
            task = TrainingTask.objects.get(pk=item["id"], schedule_slot=slot) if item["id"] else None
            if task:
                current = service.task_snapshot(task)
                if "subtasks" not in item["before"]:
                    current.pop("subtasks")
                if current != item["before"] or task.updated_at.isoformat() != item["updated_at"]:
                    raise ValidationError("任务已经变化，请重新申请。")
            values = item["after"]
            if values.get("cancel"):
                result = service.cancel_task(task, actor, values["reason"], _approved=True)
            else:
                result = service.save_slot_task(
                    slot, actor, values, task=task, publish=item["publish"], _approved=True,
                    _expected_shared_tasks=item.get("shared_tasks"),
                )
    if schedule:
        service._apply_changes(plan, schedule, actor, approved=True)
    return result


def affected_coach_ids(plan, payload):
    coach_ids, slot_ids, day_ids = set(), set(), set()
    for item in payload:
        kind = item["type"]
        if kind not in {"slot", "day", "task"}:
            continue
        before, after = item["before"], item["after"]
        if kind == "slot":
            coach_ids.update(before["coaches"])
            coach_ids.update(item.get("roster", after["coaches"]))
        elif kind == "day":
            new_duty = item.get("roster", after["duty_coaches"])
            date_changed = before["date"] != after["date"]
            if date_changed or before["duty_all"] != after["duty_all"] or set(before["duty_coaches"]) != set(new_duty):
                coach_ids.update(before["duty_coaches"])
                coach_ids.update(new_duty)
            if date_changed:
                day_ids.add(item["id"])
        elif kind == "task":
            slot_ids.add(item["slot"])
            slot_ids.update(peer["slot"] for peer in item.get("shared_tasks", ()))
    if slot_ids or day_ids:
        coach_ids.update(
            TrainingScheduleSlot.objects.filter(day__training_plan=plan, coaches__isnull=False)
            .filter(Q(pk__in=slot_ids) | Q(day_id__in=day_ids)).values_list("coaches", flat=True)
        )
    return coach_ids


@transaction.atomic
def create_change(plan, user, payload, reason, *, consultation_confirmed=False):
    if not reason.strip():
        raise ValidationError("请填写调整原因和实际执行情况。")

    class PreviewRollback(Exception):
        pass

    try:
        with transaction.atomic():
            apply_payload(plan, deepcopy(payload), user)
            raise PreviewRollback
    except PreviewRollback:
        pass
    plan.refresh_from_db()
    for item in payload:
        if item["type"] == "slot" and item["after"]["coaches_all"] and not item["before"]["coaches_all"]:
            item["roster"] = sorted(service.coach_ids(plan))
        if item["type"] == "day" and item["after"]["duty_all"] and not item["before"]["duty_all"]:
            item["roster"] = sorted(service.duty_ids(plan))
        if item["type"] == "task" and item["after"].get("assign_all"):
            item["roster"] = list(plan.participants.filter(is_active=True).order_by("user_id").values_list("user_id", flat=True))
    confirmed_at = timezone.now() if consultation_confirmed is True else None
    required_coaches = sorted(affected_coach_ids(plan, payload) - {user.pk}) if confirmed_at is None else []
    if required_coaches:
        active = get_user_model().objects.filter(pk__in=required_coaches, is_active=True)
        with_permission = get_users_with_explicit_permission("training.view_trainingplan", active)
        eligible = active.filter(Q(is_superuser=True) | Q(pk__in=with_permission.values("pk")))
        if eligible.count() != len(required_coaches):
            raise ValidationError("有相关教练无法在线确认。请先与相关教练线下沟通并取得同意，再勾选确认后提交。")
    confirmations = [{"user_id": pk, "decision": "", "note": "", "at": None} for pk in required_coaches]
    change = TrainingScheduleChange.objects.create(
        training_plan=plan, requested_by=user, reason=reason, payload=payload, consultation_confirmed_at=confirmed_at,
        confirmations=confirmations,
    )
    if required_coaches:
        change.confirmation_users.set(required_coaches)
    recorded_confirmation = (
        {"线下沟通确认时间": confirmed_at.isoformat()} if confirmed_at else {"教练确认": confirmations}
    )
    service.audit(
        plan, user, "提交调整申请", after={"申请": change.pk, "调整": payload, **recorded_confirmation},
        reason=reason,
    )
    return change


def pending_coach_ids(change):
    if change.legacy_consultation_assumed_at:
        return []
    return [step["user_id"] for step in change.confirmations if not step["decision"]]


def can_review(user, change):
    if change.status != "pending" or not user.is_active or not user.has_perm("training.view_trainingplan"):
        return False
    pending = pending_coach_ids(change)
    return user.pk in pending if pending else service.can_approve(user, change.training_plan)


@transaction.atomic
def request_task_change(plan, slot, task, user, values, publish, *, consultation_confirmed=False,
                        shared_tasks=(), written_files=None):
    from .models import TrainingChangeAttachment

    attachments = values.get("attachments", [])
    if attachments and not user.has_perm("training.add_trainingtaskattachment"):
        raise PermissionDenied
    item = {"type": "task", "id": task.pk if task else None, "slot": slot.pk, "revision": slot.revision,
            "before": service.task_snapshot(task) if task else {}, "updated_at": task.updated_at.isoformat() if task else None,
            "after": {key: [] if key == "attachments" else value for key, value in values.items()}, "publish": publish,
            "shared_tasks": service.shared_task_versions(shared_tasks)}
    change = create_change(plan, user, [item], values.get("reason", ""), consultation_confirmed=consultation_confirmed)
    pending_files = []
    for file in attachments:
        attachment = TrainingChangeAttachment(change=change, file=file, original_filename=Path(file.name).name, uploaded_by=user)
        attachment.full_clean()
        pending_files.append(attachment)
    for attachment in pending_files:
        attachment.file.seek(0)
        attachment.save()
        if written_files is not None:
            written_files.append((attachment.file.storage, attachment.file.name))
    return change


def review(change, user, *, approve, note="", stage=None):
    written_files = []
    try:
        with transaction.atomic():
            return _review(change, user, approve=approve, note=note, stage=stage, written_files=written_files)
    except Exception:
        # 文件系统不随数据库回滚；只清理本次新复制的正式文件，不触碰申请原件。
        for storage, name in written_files:
            storage.delete(name)
        raise


def _review(change, user, *, approve, note, stage, written_files):
    plan = TrainingPlan.objects.select_for_update().get(pk=change.training_plan_id)
    change = TrainingScheduleChange.objects.select_for_update().select_related("training_plan").get(pk=change.pk)
    if change.status != "pending":
        raise ValidationError("该申请已经审批，不能重复处理。")
    if not can_review(user, change):
        raise PermissionDenied
    pending = pending_coach_ids(change)
    if stage is not None and stage != ("coach" if pending else "final"):
        raise ValidationError("申请已进入下一审批阶段，请刷新后处理。")
    if pending:
        step = next(step for step in change.confirmations if step["user_id"] == user.pk and not step["decision"])
        step.update(decision="approve" if approve else "reject", note=note, at=timezone.now().isoformat())
        if approve:
            change.save(update_fields=["confirmations", "updated_at"])
            service.audit(plan, user, "教练同意调整", after={"申请": change.pk, "教练确认": change.confirmations}, reason=change.reason)
            return change
    elif approve:
        for item in change.payload:
            kind = item["type"]
            if "roster" in item:
                if kind == "task":
                    roster = set(plan.participants.filter(is_active=True).values_list("user_id", flat=True))
                else:
                    roster = service.duty_ids(plan) if kind == "day" else service.coach_ids(plan)
                if set(item["roster"]) != roster:
                    raise ValidationError("计划人员名单已变化，请重新提交调整申请。")
            if kind in {"day", "slot", "swap"} and not service.can_schedule(change.requested_by, plan):
                raise ValidationError("申请人已无排班权限，请重新申请。")
            if kind == "times" and not service.plan_manager(change.requested_by, plan):
                raise ValidationError("申请人已无计划修改权限，请重新申请。")
        result = apply_payload(plan, change.payload, change.requested_by)
        if isinstance(result, TrainingTask):
            from django.core.files import File
            from .models import TrainingTaskAttachment
            for attachment in change.attachments.all():
                with attachment.file.open("rb") as source:
                    target = TrainingTaskAttachment(training_task=result, original_filename=attachment.original_filename, uploaded_by=attachment.uploaded_by)
                    target.file.save(attachment.original_filename, File(source), save=False)
                    written_files.append((target.file.storage, target.file.name))
                    target.save()
    change.status = "approved" if approve else "rejected"
    change.reviewed_by, change.reviewed_at, change.review_note = user, timezone.now(), note
    change.save()
    service.audit(plan, user, "批准调整" if approve else "驳回调整", after={"申请": change.pk, "调整": change.payload, "意见": note, "教练确认": change.confirmations}, reason=change.reason)
    return change


def swap_snapshot(slot):
    return {"date": slot.day.date.isoformat(), "day_id": slot.day_id, "revision": slot.revision, "tasks": [{"id": task.pk, "updated_at": task.updated_at.isoformat()} for task in slot.tasks.order_by("pk")], **service.slot_snapshot(slot)}


def apply_swap(plan, item):
    slots = list(TrainingScheduleSlot.objects.select_for_update().filter(pk__in=item["slots"], day__training_plan=plan).select_related("day__training_plan").order_by("pk"))
    by_id = {slot.pk: slot for slot in slots}
    if set(by_id) != set(item["slots"]) or len(by_id) != 2:
        raise ValidationError("交换时段无效。")
    left, right = (by_id[pk] for pk in item["slots"])
    if left.day_id == right.day_id or left.period != right.period:
        raise ValidationError("请选择两个不同日期的相同时段。")
    if not left.is_configured or not right.is_configured:
        raise ValidationError("未设置的时段不能交换排班。")
    expected = [{**snapshot, "tasks": [{key: value for key, value in task.items() if key != "title"} for task in snapshot["tasks"]]} for snapshot in item["before"]]
    if [swap_snapshot(left), swap_snapshot(right)] != expected:
        raise ValidationError("待交换排班已经变化，请重新申请。")
    left_day, right_day = left.day, right.day
    left_times, right_times = (left.starts_at, left.ends_at), (right.starts_at, right.ends_at)
    period = left.period
    TrainingScheduleSlot.objects.filter(pk=left.pk).update(period=f"tmp{left.pk}", updated_at=timezone.now())
    right.day, right.starts_at, right.ends_at = left_day, *left_times
    right.revision += 1
    right.save()
    left.day, left.starts_at, left.ends_at, left.period = right_day, *right_times, period
    left.revision += 1
    left.save()
    for slot in (left, right):
        for task in slot.tasks.select_for_update():
            service._sync_task(task, slot, approved=True)


@transaction.atomic
def swap_schedule(plan, user, first, second, periods, include_duty, reason):
    raise ValidationError("本版本暂不开放快捷调班。")
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    if not service.can_schedule(user, plan):
        raise PermissionDenied
    if first == second or not periods and not include_duty or not set(periods).issubset(TrainingScheduleSlot.Period.values):
        raise ValidationError("请选择不同的日期及需要交换的内容。")
    days = {day.pk: day for day in plan.schedule_days.filter(pk__in=[first, second])}
    if len(days) != 2:
        raise ValidationError("日期必须属于本计划。")
    payload = []
    for period in dict.fromkeys(periods):
        left, right = (days[pk].slots.get(period=period) for pk in (first, second))
        if not left.is_configured or not right.is_configured:
            raise ValidationError("未设置的时段不能交换排班。")
        payload.append({"type": "swap", "slots": [left.pk, right.pk], "before": [swap_snapshot(left), swap_snapshot(right)]})
    if include_duty:
        left, right = (days[pk] for pk in (first, second))
        for day, other in ((left, right), (right, left)):
            before = service.day_snapshot(day)
            after = before | {key: service.day_snapshot(other)[key] for key in ("duty_all", "duty_coaches", "note")}
            payload.append({"type": "day", "id": day.pk, "revision": day.revision, "before": before, "after": after})
    if plan.schedule_published_at or payload_expired(plan, payload):
        return create_change(plan, user, payload, reason)
    apply_payload(plan, payload, user)
    service.audit(plan, user, "快捷交换排班", after={"调整": payload})
