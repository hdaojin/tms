"""训练排班及计划内任务的事务入口。"""

from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone

from .models import (
    TaskExecution,
    TrainingChangeRecord,
    TrainingPlan,
    TrainingScheduleDay,
    TrainingScheduleSlot,
    TrainingTask,
    TrainingTaskCoach,
    TrainingTaskDomain,
    TrainingTaskSkill,
)


ACTIVE_KINDS = {"technical", "general"}


def privileged(user):
    return user.is_active and user.is_superuser


def _in_role(user, plan, name):
    cache_name = f"_schedule_role_{name}"
    if not hasattr(plan, cache_name):
        setattr(plan, cache_name, {person.pk for person in getattr(plan, name).all()})
    return user.pk in getattr(plan, cache_name)


def plan_manager(user, plan):
    return privileged(user) or (
        user.has_perm("training.change_trainingplan")
        and (plan.created_by_id == user.pk or can_schedule(user, plan))
    )


def can_schedule(user, plan):
    return privileged(user) or (
        user.has_perm("training.schedule_trainingplan")
        and _in_role(user, plan, "schedulers")
    )


def can_approve(user, plan):
    return privileged(user) or (user.has_perm("training.approve_trainingplan") and _in_role(user, plan, "approvers"))


def task_manager(user, plan):
    return can_schedule(user, plan)


def visible_plans(user):
    if not user.has_perm("training.view_trainingplan"):
        return TrainingPlan.objects.none()
    if privileged(user):
        return TrainingPlan.objects.all()
    return TrainingPlan.objects.filter(
        Q(created_by=user)
        | Q(schedulers=user)
        | Q(approvers=user)
        | Q(schedule_days__slots__coaches=user)
        | Q(schedule_changes__confirmation_users=user)
        | (
            (Q(participants__user=user) | Q(tasks__executions__user=user) | Q(schedule_days__slots__coaches=user) | Q(schedule_days__duty_coaches=user))
            & Q(published_at__isnull=False)
        )
    ).distinct()


def staff(user, plan):
    return plan_manager(user, plan) or can_schedule(user, plan) or can_approve(user, plan) or task_manager(user, plan)


def can_fill(user, slot, *, create=False, skills_only=False):
    plan = slot.day.training_plan
    if not plan.published_at or not plan.schedule_published_at or not slot_complete(slot) or slot.kind not in ACTIVE_KINDS:
        return False
    permission = "training.add_trainingtask" if create else "training.change_trainingtask"
    if not user.has_perm(permission):
        return False
    return privileged(user) or can_schedule(user, plan) or (
        any(coach.pk == user.pk for coach in slot.coaches.all())
    )


def audit(plan, user, action, *, before=None, after=None, reason="", task=None):
    record = TrainingChangeRecord.objects.create(
        training_plan=plan,
        actor=user,
        action=action,
        before=before or {},
        after=after or {},
        reason=reason,
        task=task,
    )
    TrainingPlan.objects.filter(pk=plan.pk).update(updated_at=timezone.now())
    return record


def day_snapshot(day):
    return {
        "date": day.date.isoformat(),
        "duty_all": day.duty_all,
        "duty_coaches": sorted(person.pk for person in day.duty_coaches.all()),
        "note": day.note,
        "has_been_filled": day.has_been_filled,
    }


def slot_snapshot(slot):
    return {
        "period": slot.period,
        "kind": slot.kind,
        "domains": sorted(domain.pk for domain in slot.domains.all()),
        "primary_domain": slot.primary_domain_id,
        "coaches_all": slot.coaches_all,
        "coaches": sorted(person.pk for person in slot.coaches.all()),
        "has_been_filled": slot.has_been_filled,
    }


def task_snapshot(task):
    return {
        name: getattr(task, name)
        for name in (
            "title",
            "description",
            "requirements",
            "estimated_minutes",
            "priority",
            "order",
            "status",
            "assign_all",
        )
    } | {
        "skills": sorted(link.skill_id for link in task.skill_links.all()),
        "selected_competitors": sorted(person.pk for person in task.selected_competitors.all()),
    }



def coach_ids(plan):
    return set(plan.training_cycle.members.filter(role="coach").values_list("user_id", flat=True))


@transaction.atomic
def initialize_schedule(plan):
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    if plan.schedule_published_at:
        return
    # 兼容显式初始化旧调用；正常新建表单始终提交计划自己的八个时间字段。
    if not any(getattr(plan, name) for name in TrainingPlan.TIME_FIELDS):
        configs = period_configs()
        for period, config in configs.items():
            setattr(plan, f"{period}_start", config.start_time)
            setattr(plan, f"{period}_end", config.end_time)
        plan.save(update_fields=[*TrainingPlan.TIME_FIELDS, "updated_at"])
    plan.full_clean()
    current = plan.start_date
    while current <= plan.end_date:
        day, _ = TrainingScheduleDay.objects.get_or_create(training_plan=plan, date=current)
        for period, _label in TrainingScheduleSlot.Period.choices:
            start = getattr(plan, f"{period}_start")
            end = getattr(plan, f"{period}_end")
            TrainingScheduleSlot.objects.get_or_create(
                day=day, period=period, defaults={
                    "is_configured": start is not None,
                    "kind": "pending" if start else "unused",
                    "starts_at": timezone.make_aware(datetime.combine(current, start), timezone.get_default_timezone()) if start else None,
                    "ends_at": timezone.make_aware(datetime.combine(current, end), timezone.get_default_timezone()) if end else None,
                }
            )
        current += timedelta(days=1)


def period_configs():
    from .models import TrainingPeriodConfig
    configs = {config.period: config for config in TrainingPeriodConfig.objects.all()}
    if set(configs) != set(TrainingScheduleSlot.Period.values):
        raise ValidationError("请管理员先完整配置四个训练时段的开始、结束时间。")
    previous_end = None
    for period in TrainingScheduleSlot.Period.values:
        config = configs[period]
        config.full_clean()
        if previous_end and config.start_time < previous_end:
            raise ValidationError("四个训练时段不能重叠，须按早读、上午、下午、晚上顺序配置。")
        previous_end = config.end_time
    return configs


def plan_snapshot(plan):
    return {
        "标题": plan.title,
        "状态": plan.status,
        "周期": plan.training_cycle_id,
        "开始日期": plan.start_date.isoformat(),
        "结束日期": plan.end_date.isoformat(),
        "训练目标": plan.objective,
        "计划已发布": bool(plan.published_at),
        "时段时间": {name: getattr(plan, name).isoformat() if getattr(plan, name) else None for name in TrainingPlan.TIME_FIELDS},
        "原始文件": plan.source_file.name if plan.source_file else "",
        "参与选手": sorted(plan.participants.filter(is_active=True).values_list("user_id", flat=True)),
        "创建时选手": sorted(plan.participants.filter(was_initial=True).values_list("user_id", flat=True)),
        **{
            label: sorted(getattr(plan, field).values_list("pk", flat=True))
            for field, label in (("schedulers", "排班人员"), ("approvers", "审批人员"), ("task_managers", "任务管理员"))
        },
    }


@transaction.atomic
def save_plan_definition(form, user, *, publish=False):
    before = {}
    if form.instance.pk:
        previous = TrainingPlan.objects.select_for_update().get(pk=form.instance.pk)
        if not plan_manager(user, previous):
            raise PermissionDenied
        if previous.schedule_published_at != form.instance.schedule_published_at:
            raise ValidationError("排班状态已经变化，请刷新后重新提交。")
        # 持锁后重新执行日期、状态与关闭规则校验，不能用旧表单覆盖新状态。
        form.clean()
        if form.errors:
            raise ValidationError("计划已经变化，请根据表单提示重新提交。")
        before = plan_snapshot(previous)
    else:
        if not user.has_perm("training.add_trainingplan"):
            raise PermissionDenied
        form.instance.created_by = user
    creating = not form.instance.pk
    pending_times = None
    if not creating and set(TrainingPlan.TIME_FIELDS).intersection(form.changed_data):
        from .change_workflow import time_snapshot
        for period in ("early", "evening"):
            if form.cleaned_data.get(f"{period}_start") is None:
                slots = TrainingScheduleSlot.objects.filter(
                    day__training_plan=previous, period=period, is_configured=True, ends_at__gt=timezone.now()
                )
                if slots.exclude(kind__in=["pending", "unused"]).exists() or slots.filter(
                    Q(domains__isnull=False) | Q(coaches__isnull=False)
                ).exists() or TrainingTask.objects.filter(schedule_slot__in=slots).exclude(status="cancelled").exists():
                    raise ValidationError("请先处理该时段已有的排班和任务，再停用时段。")
        pending_times = {"type": "times", "id": previous.pk, "before": time_snapshot(previous),
                         "after": {name: form.cleaned_data[name].isoformat() if form.cleaned_data[name] else None for name in TrainingPlan.TIME_FIELDS},
                         "include_past": False}
        if previous.schedule_published_at:
            for name in TrainingPlan.TIME_FIELDS:
                setattr(form.instance, name, getattr(previous, name))
    plan = form.save()
    if pending_times:
        from .change_workflow import create_change, apply_time_change
        if previous.schedule_published_at:
            create_change(plan, user, [pending_times], form.cleaned_data.get("reason", ""))
            plan._time_change_requested = True
        else:
            apply_time_change(plan, pending_times, check_before=False)
    if publish and not plan.published_at:
        plan.published_at = timezone.now()
        plan.status = "published"
        plan.save(update_fields=["published_at", "status", "updated_at"])
        audit(plan, user, "发布计划")
    if creating:
        initialize_schedule(plan)
    audit(plan, user, "保存计划及职责", before=before, after=plan_snapshot(plan))
    return plan


def validate_day(plan, values):
    from datetime import date

    try:
        when = date.fromisoformat(values["date"])
    except (ValueError, TypeError):
        raise ValidationError("日期格式不正确。")
    if not plan.start_date <= when <= plan.end_date:
        raise ValidationError("安排日期必须位于计划范围内。")
    if not set(values["duty_coaches"]).issubset(coach_ids(plan)):
        raise ValidationError("值班人员必须是本周期教练。")
    if values["duty_all"] and not coach_ids(plan):
        raise ValidationError("本周期暂无教练，不能选择全体值班。")


def validate_slot(plan, values, *, publishing=False):
    if (
        values["period"] not in TrainingScheduleSlot.Period.values
        or values["kind"] not in TrainingScheduleSlot.Kind.values
    ):
        raise ValidationError("时段或类型不正确。")
    if values["kind"] in {"rest", "unused"}:
        values.update(domains=[], primary_domain=None)
    domains = set(values["domains"])
    if len(domains) > 1:
        raise ValidationError("每个时段最多设置一个训练领域。")
    values["primary_domain"] = next(iter(domains), None)
    allowed = set(plan.training_cycle.skill_tree_version_links.values_list("technical_domain_id", flat=True))
    if not domains.issubset(allowed):
        raise ValidationError("只能选择周期已绑定的技术领域。")
    if values["primary_domain"] and values["primary_domain"] not in domains:
        raise ValidationError("主要领域必须包含在所选领域中。")
    coaches = set(values["coaches"])
    if not coaches.issubset(coach_ids(plan)):
        raise ValidationError("负责人员必须是本周期教练。")
    if publishing:
        if values["kind"] == "pending":
            raise ValidationError("发布前请完成所有待排班时段。")
        if values["kind"] == "technical" and (not domains or not values["primary_domain"]):
            raise ValidationError("技术训练必须选择领域和主要领域。")
        if (
            values["kind"] in ACTIVE_KINDS
            and not values["coaches_all"]
            and not coaches
        ):
            raise ValidationError("训练或活动必须指定负责教练，或选择全体。")
        if values["kind"] in ACTIVE_KINDS and values["coaches_all"] and not coach_ids(plan):
            raise ValidationError("全体负责需要周期内至少有一名教练。")


def _sync_task(task, slot, *, approved=False):
    from .models import TrainingAssignmentCoach

    for execution in task.executions.all():
        for coach_id in set(slot.coaches.values_list("pk", flat=True)) | set(task.coach_links.values_list("user_id", flat=True)):
            TrainingAssignmentCoach.objects.get_or_create(execution=execution, user_id=coach_id)
    task._definition_approved = approved
    task.planned_date = slot.day.date
    task.save(update_fields=["planned_date", "updated_at"])
    # 审批入口已经校验执行锁定；仅在领域实际变化时重建，人员交接不触碰锁定领域。
    domains = set(slot.domains.values_list("pk", flat=True))
    existing = dict(task.domain_links.values_list("technical_domain_id", "role"))
    expected = {pk: "primary" if pk == slot.primary_domain_id else "related" for pk in domains}
    if existing != expected:
        task.domain_links.all().delete()
        for pk, role in expected.items():
            TrainingTaskDomain.objects.create(training_task=task, technical_domain_id=pk, role=role)
    task.coach_links.all().delete()
    for pk in slot.coaches.values_list("pk", flat=True):
        TrainingTaskCoach.objects.create(
            training_task=task, user_id=pk
        )


def _apply_changes(plan, payload, actor=None, *, approved=False, draft_import=False):
    if not plan.published_at:
        raise ValidationError("请先发布计划，再填写排班。")
    days = {obj.pk: obj for obj in plan.schedule_days.select_for_update().all()}
    slots = {
        obj.pk: obj
        for obj in TrainingScheduleSlot.objects.select_for_update()
        .filter(day__training_plan=plan)
        .select_related("day__training_plan")
    }
    time_by_date = {(slot.day.date, slot.period): (slot.starts_at, slot.ends_at) for slot in slots.values()}
    seen = set()
    for change in payload:
        key = (change["type"], change["id"])
        if key in seen:
            raise ValidationError("同一条目不能重复提交。")
        seen.add(key)
        obj = (days if change["type"] == "day" else slots).get(change["id"])
        if not obj or obj.revision != change["revision"]:
            raise ValidationError("安排已经变化，请刷新后重新提交。")
        if change["before"] != (day_snapshot(obj) if change["type"] == "day" else slot_snapshot(obj)):
            raise ValidationError("安排已经变化，请刷新后重新提交。")
        values = change["after"]
        if change["type"] == "day":
            if values["duty_all"] and values["duty_coaches"] and (not obj.duty_all or values["duty_coaches"] != change["before"]["duty_coaches"]):
                raise ValidationError("全体值班与具体名单不能同时选择。")
            if not approved and day_snapshot(obj) != values and any(slot.is_locked for slot in obj.slots.filter(is_configured=True)):
                if any(day_snapshot(obj)[field] != values[field] for field in ("date", "duty_all", "duty_coaches")):
                    raise ValidationError("当日已有锁定时段，不能修改日期或值班教练。")
            if plan.schedule_published_at and values["duty_all"]:
                if not change["before"]["duty_all"] or values["duty_coaches"] != change["before"]["duty_coaches"]:
                    values["duty_coaches"] = sorted(coach_ids(plan))
            validate_day(plan, values)
            if obj.date.isoformat() != values["date"]:
                if not approved and any(task.is_locked for task in TrainingTask.objects.filter(schedule_slot__day=obj)):
                    raise ValidationError("已有任务开始执行，不能移动日期。")
        else:
            if values["coaches_all"] and values["coaches"] and (not obj.coaches_all or values["coaches"] != change["before"]["coaches"]):
                raise ValidationError("全体负责与具体名单不能同时选择。")
            if not obj.is_configured:
                raise ValidationError("该时段未设置，不能安排训练。")
            if obj.is_locked and not approved:
                raise ValidationError("时段已锁定，不能调整排班。")
            if plan.schedule_published_at and values["coaches_all"]:
                if not change["before"]["coaches_all"] or values["coaches"] != change["before"]["coaches"]:
                    values["coaches"] = sorted(coach_ids(plan))
            validate_slot(plan, values, publishing=not draft_import or bool(change.get("import_task")))
            before = slot_snapshot(obj)
            tasks = list(obj.tasks.select_for_update().exclude(status="cancelled"))
            if change.get("import_task") and tasks:
                raise ValidationError("目标时段已有任务，请重新预览导入；不能覆盖或重复导入。")
            if tasks and values["kind"] not in ACTIVE_KINDS:
                if any(task.status != "cancelled" for task in tasks):
                    raise ValidationError("请先取消该时段的现有任务，再改为休息或不安排。")
            protected = ("period", "kind", "domains", "primary_domain")
            if not approved and any(before[field] != values[field] for field in protected) and any(task.is_locked for task in tasks):
                raise ValidationError("时段已锁定，不能调整排班。")
            # 保证已有技能仍与新领域相容。
            if set(values["domains"]) != set(before["domains"]):
                for task in tasks:
                    validate_skills(task, list(task.skill_links.values_list("skill_id", flat=True)), values["domains"])
    # 时段互换先腾出唯一键，所有对象仍位于同一事务中。
    for change in payload:
        if change["type"] == "day" and days[change["id"]].date.isoformat() != change["after"]["date"]:
            from datetime import date

            TrainingScheduleDay.objects.filter(pk=change["id"]).update(
                date=date(1, 1, 1) + timedelta(days=change["id"])
            )
        if change["type"] == "slot" and slots[change["id"]].period != change["after"]["period"]:
            TrainingScheduleSlot.objects.filter(pk=change["id"]).update(period=f"tmp{change['id']}")
    all_coaches = coach_ids(plan)
    for change in payload:
        values = change["after"]
        obj = (days if change["type"] == "day" else slots)[change["id"]]
        fields = (
            ("date", "duty_all", "note")
            if change["type"] == "day"
            else ("period", "kind", "primary_domain_id", "coaches_all")
        )
        for field in fields:
            value = values[field.removesuffix("_id")]
            if field == "date":
                from datetime import date
                value = date.fromisoformat(value)
            setattr(obj, field, value)
        if change["type"] == "slot" and obj.period != change["before"]["period"]:
            obj.starts_at, obj.ends_at = time_by_date[(obj.day.date, obj.period)]
        obj.has_been_filled = True
        obj.revision += 1
        obj.save()
        if change["type"] == "day":
            from datetime import date
            delta = obj.date - date.fromisoformat(change["before"]["date"])
            if delta.days:
                for slot in obj.slots.all():
                    if slot.starts_at and slot.ends_at:
                        slot.starts_at, slot.ends_at = time_by_date[(obj.date, slot.period)]
                        slot.save(update_fields=["starts_at", "ends_at", "updated_at"])
            previous_all = change["before"]["duty_all"]
            snapshot = values["duty_coaches"] if previous_all else all_coaches
            obj.duty_coaches.set(snapshot if obj.duty_all and plan.schedule_published_at else values["duty_coaches"])
            obj.slots.update(revision=F("revision") + 1, updated_at=timezone.now())
        else:
            obj.domains.set(values["domains"])
            previous_all = change["before"]["coaches_all"]
            snapshot = values["coaches"] if previous_all else all_coaches
            obj.coaches.set(snapshot if obj.coaches_all and plan.schedule_published_at else values["coaches"])
    # 最终结构检查在事务内完成，避免互换时产生半完成状态。
    for day in days.values():
        periods = list(day.slots.values_list("period", flat=True))
        if len(periods) != 4 or set(periods) != set(TrainingScheduleSlot.Period.values):
            raise ValidationError("每天必须保留四个不同的时段。")
    actual_dates = set(plan.schedule_days.values_list("date", flat=True))
    expected_dates = {
        plan.start_date + timedelta(days=index) for index in range((plan.end_date - plan.start_date).days + 1)
    }
    if actual_dates != expected_dates:
        raise ValidationError("日期调整必须保持完整日期框架；对调请同时提交相关日期。")
    changed_days = {change["id"] for change in payload if change["type"] == "day" and change["before"]["date"] != change["after"]["date"]}
    for slot in TrainingScheduleSlot.objects.filter(day_id__in=changed_days).select_related("day__training_plan"):
        for task in slot.tasks.select_for_update().exclude(status="cancelled"):
            _sync_task(task, slot, approved=approved)
    for change in payload:
        if change["type"] == "slot":
            slot = TrainingScheduleSlot.objects.select_related("day__training_plan").get(pk=change["id"])
            for task in slot.tasks.select_for_update().exclude(status="cancelled"):
                _sync_task(task, slot, approved=approved)
            if change.get("import_task"):
                text = change["import_task"]
                save_slot_task(slot, actor, {"title": text.splitlines()[0][:180], "description": text if "\n" in text or len(text) > 180 else "", "assign_all": False, "competitors": list(plan.participants.filter(is_active=True).values_list("user_id", flat=True))}, _importing=True, _approved=approved)


def slot_complete(slot):
    if not slot.is_configured or slot.kind == "pending":
        return False
    if slot.kind in {"rest", "unused"}:
        return True
    has_coaches = bool(list(slot.coaches.all())) or (slot.coaches_all and bool(coach_ids(slot.day.training_plan)))
    return bool(has_coaches and (slot.kind == "general" or slot.primary_domain_id))


def was_filled(obj):
    if obj.has_been_filled:
        return True
    if isinstance(obj, TrainingScheduleDay):
        return bool(obj.duty_all or obj.note.strip() or list(obj.duty_coaches.all()))
    return bool(obj.is_configured and obj.kind != "pending" or list(obj.domains.all()) or
                list(obj.coaches.all()) or obj.tasks.exists())


@transaction.atomic
def save_schedule(plan, user, payload, reason=""):
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    if not can_schedule(user, plan):
        raise PermissionDenied
    if any(item.get("import_task") for item in payload):
        raise ValidationError("Excel 任务须通过空计划导入入口保存。")
    if not plan.published_at:
        raise ValidationError("请先发布计划，再填写排班。")
    if not payload:
        raise ValidationError("没有需要保存的调整。")
    initial = True
    for item in payload:
        model = TrainingScheduleDay if item["type"] == "day" else TrainingScheduleSlot
        scope = {"training_plan": plan} if item["type"] == "day" else {"day__training_plan": plan}
        obj = model.objects.select_for_update().filter(pk=item["id"], **scope).first()
        if obj is None:
            raise PermissionDenied
        initial = initial and not was_filled(obj)
        item["after"]["has_been_filled"] = True
    if plan.schedule_published_at and not initial and not reason.strip():
        raise ValidationError("修改已填写的排班或日级信息时，请填写调整原因。")
    from .change_workflow import create_change
    if not initial and plan.schedule_published_at:
        return create_change(plan, user, payload, reason)
    _apply_changes(plan, payload, user, approved=initial or not plan.schedule_published_at)
    audit(plan, user, "首次填写排班" if initial else "保存排班", after={"调整": payload}, reason=reason)


@transaction.atomic
def publish_schedule(plan, user):
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    if not can_schedule(user, plan):
        raise PermissionDenied
    if not plan.published_at:
        raise ValidationError("请先发布计划，再发布排班。")
    if plan.schedule_published_at:
        raise ValidationError("排班已经发布。")
    expected = (plan.end_date - plan.start_date).days + 1
    if plan.schedule_days.count() != expected:
        raise ValidationError("日期框架不完整，请先初始化排班。")
    all_coaches = coach_ids(plan)
    for day in plan.schedule_days.select_for_update():
        validate_day(plan, day_snapshot(day))
        active_slots = [slot for slot in day.slots.all() if slot.is_configured]
        duty_optional = bool(active_slots) and all(slot.kind in {"rest", "unused"} for slot in active_slots)
        if not duty_optional and not (day.duty_all and all_coaches or day.duty_coaches.exists()):
            raise ValidationError(f"{day.date} 尚未安排值班教练。")
        if day.slots.count() != 4:
            raise ValidationError("时段框架不完整。")
        if day.duty_all:
            day.duty_coaches.set(all_coaches)
        for slot in day.slots.all():
            if slot.is_configured:
                validate_slot(plan, slot_snapshot(slot), publishing=True)
            if slot.coaches_all:
                slot.coaches.set(all_coaches)
            for task in slot.tasks.exclude(status="cancelled"):
                _sync_task(task, slot, approved=True)
            slot.revision += 1
            slot.save(update_fields=["revision", "updated_at"])
        day.revision += 1
        day.save(update_fields=["revision", "updated_at"])
    plan.schedule_published_at = timezone.now()
    plan.save(update_fields=["schedule_published_at", "updated_at"])
    audit(plan, user, "发布排班")


def review_change(change, user, *, approve, note=""):
    from .change_workflow import review
    return review(change, user, approve=approve, note=note)


def validate_skills(task, skill_ids, domain_ids=None):
    from standards.models import Skill

    skills = list(Skill.objects.filter(pk__in=skill_ids).prefetch_related("related_domains"))
    if len(skills) != len(set(skill_ids)):
        raise ValidationError("技能不存在。")
    domains = set(
        domain_ids if domain_ids is not None else task.domain_links.values_list("technical_domain_id", flat=True)
    )
    for skill in skills:
        if skill.skill_project_id != task.skill_project.pk:
            raise ValidationError("技能必须属于计划对应项目。")
        if domains and not domains.intersection(
            {skill.primary_domain_id, *skill.related_domains.values_list("pk", flat=True)}
        ):
            raise ValidationError("技能与任务技术领域必须至少有一个交集。")


@transaction.atomic
def save_slot_task(slot, user, values, *, task=None, _importing=False, publish=False, _approved=False):
    from pathlib import Path
    from .models import TrainingTaskAttachment
    plan = TrainingPlan.objects.select_for_update().get(pk=slot.day.training_plan_id)
    slot = TrainingScheduleSlot.objects.select_for_update().select_related("day__training_plan").get(pk=slot.pk)
    import_allowed = (
        _importing and task is None and not publish and plan.published_at and not plan.schedule_published_at
        and can_schedule(user, plan) and user.has_perm("training.add_trainingtask")
    )
    if not can_fill(user, slot, create=task is None) and not import_allowed:
        raise PermissionDenied
    validate_slot(plan, slot_snapshot(slot), publishing=True)
    creating = task is None
    if task:
        task = TrainingTask.objects.select_for_update().get(pk=task.pk, schedule_slot=slot)
        if task.status == "cancelled":
            raise ValidationError("已取消任务不可编辑，请新增任务。")
    else:
        task = TrainingTask(training_plan=plan, schedule_slot=slot, planned_date=slot.day.date, created_by=user)
    _approved = _approved or task.status == "draft"
    if slot.is_locked and not _approved:
        from .change_workflow import request_task_change
        return request_task_change(plan, slot, task if task.pk else None, user, values, publish)
    task._definition_approved = _approved
    before = task_snapshot(task) if task.pk else {}
    for field in ("title", "description", "requirements", "estimated_minutes", "priority", "order", "assign_all"):
        if field in values:
            setattr(task, field, values[field])
    task.full_clean(exclude=["selected_competitors"])
    task.save()
    _sync_task(task, slot, approved=_approved)
    selected = set(values.get("competitors", before.get("selected_competitors", [])))
    valid = set(
        plan.participants.filter(is_active=True, user_id__in=selected).values_list("user_id", flat=True)
    ) | set(task.executions.filter(user_id__in=selected).values_list("user_id", flat=True))
    if selected != valid:
        raise ValidationError("只能选择本计划参与中的选手。")
    task.selected_competitors.set(selected)
    _set_skills(task, values.get("skills", before.get("skills", [])))
    if publish and task.status == "draft":
        publish_slot_task(task, user, _approved=_approved)
        task.refresh_from_db()
    elif not creating and task.status == "published" and (
        before.get("assign_all") != task.assign_all or before.get("selected_competitors") != sorted(selected)
    ):
        assign_competitors(task, user, selected=None if task.assign_all else selected, reason=values.get("reason", ""), _approved=_approved)
    audit(plan, user, "保存任务", task=task, before=before, after=task_snapshot(task))
    attachments = [TrainingTaskAttachment(training_task=task, file=file, uploaded_by=user, original_filename=Path(file.name).name) for file in values.get("attachments", [])]
    if attachments and not user.has_perm("training.add_trainingtaskattachment"):
        raise PermissionDenied
    for attachment in attachments:
        attachment.full_clean()
    for attachment in attachments:
        attachment.save()
        audit(plan, user, "添加任务附件", task=task, after={"附件": attachment.pk, "文件名": attachment.original_filename})
    return task


def _set_skills(task, skill_ids):
    skill_ids = list(dict.fromkeys(skill_ids))
    validate_skills(task, skill_ids)
    task.skill_links.all().delete()
    for index, pk in enumerate(skill_ids):
        TrainingTaskSkill.objects.create(
            training_task=task, skill_id=pk, role="primary" if index == 0 else "related", order=index
        )


@transaction.atomic
def set_task_skills(task, user, skill_ids, *, reason=""):
    plan = TrainingPlan.objects.select_for_update().get(pk=task.training_plan_id)
    task = TrainingTask.objects.select_for_update().select_related("schedule_slot__day__training_plan").get(pk=task.pk)
    allowed = (
        can_fill(user, task.schedule_slot, skills_only=True)
        if task.schedule_slot_id
        else task_manager(user, plan) and user.has_perm("training.change_trainingtask")
    )
    if not allowed:
        raise PermissionDenied
    if task.schedule_slot_id and task.schedule_slot.is_locked and task.status != "draft":
        from .change_workflow import request_task_change
        return request_task_change(plan, task.schedule_slot, task, user, {"skills": skill_ids, "reason": reason}, False)
    task._definition_approved = task.status == "draft"
    before = task_snapshot(task)
    _set_skills(task, skill_ids)
    task.save(update_fields=["updated_at"])
    audit(plan, user, "修正技能关联", task=task, before=before, after=task_snapshot(task))


@transaction.atomic
def assign_competitors(task, user, *, selected=None, _publishing=False, reason="", _importing=False, _approved=False):
    from .models import TrainingAssignmentCoach
    plan = TrainingPlan.objects.select_for_update().get(pk=task.training_plan_id)
    task = TrainingTask.objects.select_for_update().select_related("schedule_slot__day__training_plan").get(pk=task.pk)
    import_allowed = _importing and bool(plan.published_at and plan.schedule_published_at) and can_schedule(user, plan) and not task.schedule_slot.is_locked and (privileged(user) or any(coach.pk == user.pk for coach in task.schedule_slot.coaches.all()) or task.schedule_slot.coaches_all)
    if not task.schedule_slot_id or (not can_fill(user, task.schedule_slot) and not import_allowed):
        raise PermissionDenied
    if task.schedule_slot.is_locked and not _approved:
        from .change_workflow import request_task_change
        return request_task_change(plan, task.schedule_slot, task, user, {"assign_all": selected is None, "competitors": list(selected or []), "reason": reason}, False)
    task._definition_approved = _approved
    if task.status != "published" and not (_publishing and task.status == "draft"):
        raise ValidationError("只有已发布任务可以调整选手分配。")
    members = set(plan.participants.filter(is_active=True).values_list("user_id", flat=True))
    if _publishing and not task.assign_all:
        members |= set(plan.participants.filter(user_id__in=task.selected_competitors.values("pk")).values_list("user_id", flat=True))
    desired = members if selected is None else set(selected)
    if not desired.issubset(members | set(task.executions.values_list("user_id", flat=True))):
        raise ValidationError("只能分配本计划参与中的选手。")
    if not desired:
        raise ValidationError("发布或分配任务时请至少选择一名选手。")
    before = assignment_snapshot(task)
    for execution in task.executions.select_for_update():
        if execution.user_id not in desired and execution.status != "cancelled" and execution.revoked_at is None:
            if execution.started_at or execution.status != "assigned" or execution.progress_records.exists():
                raise ValidationError("已经开始的执行不能移出。")
            if not reason.strip():
                raise ValidationError("撤销分配必须填写原因。")
            execution.revoked_at, execution.revoked_by, execution.revoke_reason = timezone.now(), user, reason
            execution.save(update_fields=["revoked_at", "revoked_by", "revoke_reason", "updated_at"])
    for pk in desired:
        execution, created = TaskExecution.objects.get_or_create(training_task=task, user_id=pk)
        if not created and (execution.status == "cancelled" or execution.revoked_at) and not execution.started_at:
            execution.status = "assigned"
            execution.revoked_at, execution.revoked_by, execution.revoke_reason = None, None, ""
            execution.save(update_fields=["status", "revoked_at", "revoked_by", "revoke_reason", "updated_at"])
        for coach_id in task.schedule_slot.coaches.values_list("pk", flat=True):
            TrainingAssignmentCoach.objects.get_or_create(execution=execution, user_id=coach_id)
    task.selected_competitors.set(task.executions.filter(revoked_at__isnull=True).exclude(status="cancelled").values_list("user_id", flat=True))
    task.save(update_fields=["updated_at"])
    audit(
        plan,
        user,
        "调整选手分配",
        task=task,
        before={"执行": before},
        after={"执行": assignment_snapshot(task)},
        reason=reason,
    )


def assignment_snapshot(task):
    return [{"user_id": entry.user_id, "status": entry.status, "revoked_at": entry.revoked_at.isoformat() if entry.revoked_at else None, "revoke_reason": entry.revoke_reason} for entry in task.executions.order_by("user_id")]


@transaction.atomic
def publish_slot_task(task, user, *, _approved=False):
    plan = TrainingPlan.objects.select_for_update().get(pk=task.training_plan_id)
    task = TrainingTask.objects.select_for_update().select_related("schedule_slot__day__training_plan").get(pk=task.pk)
    if not task.schedule_slot_id or not can_fill(user, task.schedule_slot):
        raise PermissionDenied
    _approved = _approved or task.status == "draft"
    if task.schedule_slot.is_locked and not _approved:
        from .change_workflow import request_task_change
        return request_task_change(plan, task.schedule_slot, task, user, {}, True)
    task._definition_approved = _approved
    if task.status == "published":
        return task
    if task.status != "draft":
        raise ValidationError("只能发布草稿任务。")
    validate_slot(plan, slot_snapshot(task.schedule_slot), publishing=True)
    # 撤回后再次发布保留首次分配，不能因全体成员变化扩大名单。
    previously_published = task.executions.exists()
    assign_competitors(
        task,
        user,
        selected=task.selected_competitors.values_list("pk", flat=True) if previously_published or not task.assign_all else None,
        _publishing=True,
        _approved=_approved,
    )
    task.selected_competitors.set(task.executions.exclude(status="cancelled").values_list("user_id", flat=True))
    task.status = "published"
    task.save(update_fields=["status", "updated_at"])
    audit(plan, user, "发布任务", task=task)
    return task


@transaction.atomic
def cancel_task(task, user, reason, *, _approved=False):
    plan = TrainingPlan.objects.select_for_update().get(pk=task.training_plan_id)
    task = TrainingTask.objects.select_for_update().select_related("schedule_slot__day__training_plan").get(pk=task.pk)
    if not task.schedule_slot_id or not can_fill(user, task.schedule_slot):
        raise PermissionDenied
    if not reason.strip():
        raise ValidationError("取消任务需要填写原因。")
    if task.status == "published":
        raise ValidationError("请先由超级管理员撤回任务发布，再清空任务。")
    from .entry_operations import has_execution_facts
    if has_execution_facts(TrainingTask.objects.filter(pk=task.pk)):
        raise ValidationError("任务已有执行或进度事实，不能清空。")
    task._definition_approved = _approved
    if task.status == "cancelled":
        raise ValidationError("任务已经取消。")
    before = task_snapshot(task)
    task.status = "cancelled"
    task.cancelled_at, task.cancelled_by, task.cancel_reason = timezone.now(), user, reason
    task.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancel_reason", "updated_at"])
    for execution in task.executions.select_for_update().filter(status="assigned", started_at__isnull=True, progress_records__isnull=True):
        execution.revoked_at, execution.revoked_by, execution.revoke_reason = timezone.now(), user, reason
        execution.save(update_fields=["revoked_at", "revoked_by", "revoke_reason", "updated_at"])
    audit(plan, user, "取消任务", task=task, before=before, after=task_snapshot(task), reason=reason)


@transaction.atomic
def attach_legacy_task(task, slot, user):
    plan = TrainingPlan.objects.select_for_update().get(pk=task.training_plan_id)
    if not task_manager(user, plan) or not user.has_perm("training.change_trainingtask"):
        raise PermissionDenied
    task = TrainingTask.objects.select_for_update().get(pk=task.pk)
    slot = TrainingScheduleSlot.objects.select_for_update().select_related("day__training_plan").get(pk=slot.pk)
    if task.schedule_slot_id or task.is_locked or slot.is_locked or slot.day.training_plan_id != plan.pk:
        raise ValidationError("只能整理本计划尚未开始且未分时段的历史任务。")
    if slot.kind not in ACTIVE_KINDS:
        raise ValidationError("请选择已发布的训练或活动时段。")
    validate_skills(
        task, list(task.skill_links.values_list("skill_id", flat=True)), slot.domains.values_list("pk", flat=True)
    )
    task.schedule_slot = slot
    task.planned_date = slot.day.date
    task.assign_all = False
    task.save()
    task.selected_competitors.set(task.executions.exclude(status="cancelled").values_list("user_id", flat=True))
    _sync_task(task, slot)
    audit(plan, user, "整理历史任务", task=task, after={"时段": str(slot)})
