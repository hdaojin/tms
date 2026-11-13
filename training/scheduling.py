"""训练排班及计划内任务的事务入口。"""

from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from .models import (
    TaskExecution,
    TrainingBoardPlan,
    TrainingChangeRecord,
    TrainingPlan,
    TrainingPlanStaff,
    TrainingScheduleDay,
    TrainingScheduleSlot,
    TrainingTask,
    TrainingTaskCoach,
    TrainingTaskDomain,
    TrainingTaskSkill,
)


SLOT_KIND = TrainingScheduleSlot.Kind
SPECIAL_DOMAIN_KINDS = {
    "comprehensive": SLOT_KIND.COMPREHENSIVE,
    "other": SLOT_KIND.GENERAL,
    "rest": SLOT_KIND.REST,
    "unused": SLOT_KIND.UNUSED,
}
SPECIAL_DOMAIN_CHOICES = [(choice, kind.label) for choice, kind in SPECIAL_DOMAIN_KINDS.items()]
SPECIAL_DOMAIN_BY_KIND = {kind: choice for choice, kind in SPECIAL_DOMAIN_KINDS.items()}
ACTIVE_KINDS = {SLOT_KIND.TECHNICAL, SLOT_KIND.GENERAL, SLOT_KIND.COMPREHENSIVE}


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


def _plan_has_relation(**filters):
    # 独立检查每个关系，避免多个一对多关系在同一查询中相乘。
    return Exists(TrainingPlan.objects.filter(pk=OuterRef("pk"), **filters))


def visible_plans(user):
    if not user.has_perm("training.view_trainingplan"):
        return TrainingPlan.objects.none()
    if privileged(user):
        return TrainingPlan.objects.all()
    return TrainingPlan.objects.filter(
        Q(created_by=user)
        | _plan_has_relation(schedulers=user)
        | _plan_has_relation(approvers=user)
        | _plan_has_relation(schedule_days__slots__coaches=user)
        | _plan_has_relation(
            staff_members__user=user, staff_members__role=TrainingPlanStaff.Role.COACH, staff_members__is_active=True,
        )
        | _plan_has_relation(schedule_changes__confirmation_users=user)
        | (
            (
                _plan_has_relation(participants__user=user)
                | _plan_has_relation(tasks__executions__user=user)
                | _plan_has_relation(schedule_days__duty_coaches=user)
            )
            & Q(published_at__isnull=False)
        )
    )


def my_plans(queryset, user):
    return queryset.filter(
        _plan_has_relation(participants__user=user, participants__is_active=True)
        | _plan_has_relation(
            staff_members__user=user, staff_members__role=TrainingPlanStaff.Role.COACH, staff_members__is_active=True,
        )
        | _plan_has_relation(schedulers=user)
        | _plan_has_relation(schedule_days__slots__coaches=user)
    )


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
            "overview",
            "subtasks",
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
    return set(plan.responsible_coaches.values_list("pk", flat=True))


def duty_ids(plan):
    return set(plan.duty_personnel.values_list("pk", flat=True))


def check_roster_removal(plan, role, removed):
    if not removed:
        return
    now, today = timezone.now(), timezone.localdate()
    slots = TrainingScheduleSlot.objects.filter(day__training_plan=plan, is_configured=True).filter(
        Q(ends_at__gt=now) | Q(ends_at__isnull=True, day__date__gte=today)
    )
    if role == "responsible_coaches":
        assigned = slots.filter(Q(coaches__pk__in=removed) | Q(coaches_all=True, coaches__isnull=True)).values_list("day__date", flat=True).first()
    elif role == "duty_personnel":
        assigned = plan.schedule_days.filter(
            Q(duty_coaches__pk__in=removed) | Q(duty_all=True, duty_coaches__isnull=True),
            date__gte=today,
        ).values_list("date", flat=True).first()
    else:
        tasks = plan.tasks.exclude(status="cancelled").filter(
            Q(status="draft") | Q(schedule_slot__in=slots) |
            Q(schedule_slot__isnull=True, planned_date__gte=today)
        )
        assigned = tasks.filter(
            Q(selected_competitors__pk__in=removed) | Q(status="draft", assign_all=True)
        ).values_list("planned_date", flat=True).first()
        if assigned is None:
            assigned = TaskExecution.objects.filter(
                training_task__in=tasks, user_id__in=removed, revoked_at__isnull=True
            ).exclude(status="cancelled").values_list("training_task__planned_date", flat=True).first()
    if assigned is not None:
        raise ValidationError(f"请先处理 {assigned} 的相关排班或任务分配，再移除人员。")
    keys = {
        "responsible_coaches": ("coaches", "coaches_all"),
        "duty_personnel": ("duty_coaches", "duty_all"),
        "participants": ("competitors", "assign_all"),
    }
    people, everyone = keys[role]
    for change in plan.schedule_changes.filter(status="pending"):
        for item in change.payload:
            for snapshot in (item.get("before"), item.get("after"), item.get("values")):
                for values in snapshot if isinstance(snapshot, list) else [snapshot]:
                    if isinstance(values, dict) and (
                        values.get(everyone) or removed.intersection(values.get(people, ())) or
                        role == "participants" and removed.intersection(values.get("selected_competitors", ()))
                    ):
                        raise ValidationError(f"请先处理待审批调整 #{change.pk}，再移除人员。")


def require_rosters(plan):
    if not coach_ids(plan) or not duty_ids(plan) or not plan.participants.filter(is_active=True).exists():
        raise ValidationError("请先指定负责教练、参与选手和值班人员，每类至少一人。")


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
        "实施对象": plan.implementation_audience,
        "计划已发布": bool(plan.published_at),
        "时段时间": {name: getattr(plan, name).isoformat() if getattr(plan, name) else None for name in TrainingPlan.TIME_FIELDS},
        "原始文件": plan.source_file.name if plan.source_file else "",
        "参与选手": sorted(plan.participants.filter(is_active=True).values_list("user_id", flat=True)),
        "创建时选手": sorted(plan.participants.filter(was_initial=True).values_list("user_id", flat=True)),
        **{
            label: sorted(getattr(plan, field).values_list("pk", flat=True))
            for field, label in (("schedulers", "排班人员"), ("approvers", "审批人员"), ("task_managers", "任务管理员"),
                                 ("responsible_coaches", "负责教练"), ("duty_personnel", "值班人员"))
        },
    }


def check_plan_structure_edit(plan, start_date, end_date, *, changed_periods=()):
    from .plan_clear import has_schedule_content

    if plan.published_at or plan.schedule_published_at:
        raise ValidationError("请先撤回计划发布，再修改日期范围或每日时段。")
    if plan.tasks.exclude(status="cancelled").exists() or has_schedule_content(plan):
        raise ValidationError("请先清空任务和排班，再修改日期范围或每日时段。")
    if start_date and end_date and (
        plan.tasks.filter(
            Q(planned_date__lt=start_date) | Q(planned_date__gt=end_date) |
            Q(schedule_slot__day__date__lt=start_date) | Q(schedule_slot__day__date__gt=end_date)
        ).exists()
        or plan.personal_tasks.exclude(date__range=(start_date, end_date)).exists()
    ):
        raise ValidationError("日期范围须保留已有历史任务的日期。")
    if changed_periods and plan.tasks.filter(schedule_slot__period__in=changed_periods).exists():
        raise ValidationError("每日时段已关联历史任务，不能修改时间快照。")


def _sync_empty_framework(plan, previous):
    plan.schedule_days.exclude(date__range=(plan.start_date, plan.end_date)).delete()
    changed_periods = [
        period for period in TrainingScheduleSlot.Period.values
        if any(getattr(previous, f"{period}_{edge}") != getattr(plan, f"{period}_{edge}") for edge in ("start", "end"))
    ]
    for slot in TrainingScheduleSlot.objects.filter(day__training_plan=plan, period__in=changed_periods).select_related("day"):
        start, end = (getattr(plan, f"{slot.period}_{edge}") for edge in ("start", "end"))
        slot.is_configured = start is not None
        slot.kind = "pending" if start else "unused"
        slot.starts_at = timezone.make_aware(datetime.combine(slot.day.date, start)) if start else None
        slot.ends_at = timezone.make_aware(datetime.combine(slot.day.date, end)) if end else None
        slot.revision += 1
        slot.save(update_fields=["is_configured", "kind", "starts_at", "ends_at", "revision", "updated_at"])
    initialize_schedule(plan)


@transaction.atomic
def publish_plan(plan, user):
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    if not plan_manager(user, plan):
        raise PermissionDenied
    if plan.published_at:
        raise ValidationError("计划已发布。")
    require_rosters(plan)
    plan.published_at = timezone.now()
    plan.status = "published"
    plan.save(update_fields=["published_at", "status", "updated_at"])
    audit(plan, user, "发布计划")
    return plan


@transaction.atomic
def set_board_listing(plan, user, *, enabled):
    if not privileged(user):
        raise PermissionDenied
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    if not plan.published_at:
        raise ValidationError("只有已发布的训练计划可设置上屏。")
    if enabled:
        _, changed = TrainingBoardPlan.objects.get_or_create(training_plan=plan)
    else:
        changed, _ = TrainingBoardPlan.objects.filter(training_plan=plan).delete()
    if changed:
        audit(plan, user, "加入训练大屏" if enabled else "移出训练大屏")


@transaction.atomic
def save_plan_definition(form, user):
    before = {}
    previous = None
    structure_changed = False
    if form.instance.pk:
        previous = TrainingPlan.objects.select_for_update().get(pk=form.instance.pk)
        if not plan_manager(user, previous):
            raise PermissionDenied
        if (previous.published_at, previous.schedule_published_at) != (
            form.instance.published_at, form.instance.schedule_published_at
        ):
            raise ValidationError("计划发布状态已经变化，请刷新后重新提交。")
        form.clean()
        if form.errors:
            raise ValidationError("计划已经变化，请根据表单提示重新提交。")
        before = plan_snapshot(previous)
        structure_fields = ("start_date", "end_date", *TrainingPlan.TIME_FIELDS)
        structure_changed = any(getattr(previous, name) != getattr(form.instance, name) for name in structure_fields)
    else:
        if not user.has_perm("training.add_trainingplan"):
            raise PermissionDenied
        form.instance.created_by = user
    plan = form.save()
    if previous is None:
        initialize_schedule(plan)
    elif structure_changed:
        _sync_empty_framework(plan, previous)
    audit(plan, user, "保存计划及职责", before=before, after=plan_snapshot(plan))
    return plan


def validate_day(plan, values, *, previous_people=()):
    from datetime import date

    try:
        when = date.fromisoformat(values["date"])
    except (ValueError, TypeError):
        raise ValidationError("日期格式不正确。")
    if not plan.start_date <= when <= plan.end_date:
        raise ValidationError("安排日期必须位于计划范围内。")
    if not set(values["duty_coaches"]).issubset(duty_ids(plan).union(previous_people)):
        raise ValidationError("值班人员必须在本计划的值班名单内。")
    if values["duty_all"] and not (values["duty_coaches"] or duty_ids(plan)):
        raise ValidationError("本计划暂无值班人员，不能选择全体值班。")


def validate_slot(plan, values, *, publishing=False, previous_people=()):
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
    if not coaches.issubset(coach_ids(plan).union(previous_people)):
        raise ValidationError("负责教练必须在本计划的负责教练名单内。")
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
                    raise ValidationError("当日已有锁定时段，不能修改日期或值班人员。")
            if plan.schedule_published_at and values["duty_all"]:
                if not change["before"]["duty_all"] or values["duty_coaches"] != change["before"]["duty_coaches"]:
                    values["duty_coaches"] = sorted(duty_ids(plan))
            previous_people = change["before"]["duty_coaches"] if obj.date.isoformat() == values["date"] else ()
            validate_day(plan, values, previous_people=previous_people)
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
            validate_slot(
                plan, values, publishing=not draft_import or bool(change.get("import_task")),
                previous_people=change["before"]["coaches"] if obj.is_locked else (),
            )
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
            obj.duty_coaches.set(values["duty_coaches"])
            obj.slots.update(revision=F("revision") + 1, updated_at=timezone.now())
        else:
            obj.domains.set(values["domains"])
            obj.coaches.set(values["coaches"])
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
                from .checklists import outline_items

                text = change["import_task"]
                title, *outline = text.splitlines()
                overview = text if len(title) > 180 else "\n".join(outline)
                save_slot_task(slot, actor, {
                    "title": title[:180], "overview": overview, "subtask_titles": outline_items(overview),
                    "assign_all": False,
                    "competitors": list(plan.participants.filter(is_active=True).values_list("user_id", flat=True)),
                }, _importing=True, _approved=approved)


def slot_complete(slot, *, has_plan_coaches=None):
    if not slot.is_configured or slot.kind == "pending":
        return False
    if slot.kind in {"rest", "unused"}:
        return True
    if slot.coaches_all and has_plan_coaches is None:
        has_plan_coaches = bool(coach_ids(slot.day.training_plan))
    has_coaches = bool(list(slot.coaches.all())) or (slot.coaches_all and has_plan_coaches)
    return bool(has_coaches and (
        slot.kind in {SLOT_KIND.GENERAL, SLOT_KIND.COMPREHENSIVE} or slot.primary_domain_id
    ))


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
    require_rosters(plan)
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
    require_rosters(plan)
    all_coaches = coach_ids(plan)
    all_duty = duty_ids(plan)
    for day in plan.schedule_days.select_for_update():
        day_values = day_snapshot(day)
        active_slots = [slot for slot in day.slots.all() if slot.is_configured]
        day_ended = day.date < timezone.localdate() and all(slot.is_locked for slot in active_slots)
        validate_day(plan, day_values, previous_people=day_values["duty_coaches"] if day_ended else ())
        duty_optional = bool(active_slots) and all(slot.kind in {"rest", "unused"} for slot in active_slots)
        if not duty_optional and not (day.duty_all and all_duty or day.duty_coaches.exists()):
            raise ValidationError(f"{day.date} 尚未安排值班人员。")
        if day.slots.count() != 4:
            raise ValidationError("时段框架不完整。")
        if day.duty_all and not day_values["duty_coaches"]:
            day.duty_coaches.set(all_duty)
        for slot in day.slots.all():
            values = slot_snapshot(slot)
            if slot.is_configured:
                validate_slot(
                    plan, values, publishing=True,
                    previous_people=values["coaches"] if slot.is_locked else (),
                )
            if slot.coaches_all and not values["coaches"]:
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
    creating = task is None
    snapshot = slot_snapshot(slot)
    validate_slot(
        plan, snapshot, publishing=True,
        previous_people=snapshot["coaches"] if slot.is_locked and not creating and not publish else (),
    )
    if creating or publish:
        require_rosters(plan)
    if task:
        task = TrainingTask.objects.select_for_update().get(pk=task.pk, schedule_slot=slot)
        if task.status == "cancelled":
            raise ValidationError("已取消任务不可编辑，请新增任务。")
    else:
        task = TrainingTask(training_plan=plan, schedule_slot=slot, planned_date=slot.day.date, created_by=user)
    from .checklists import update_subtasks, validate_subtask_change

    titles = values.get("subtask_titles")
    _approved = _approved or task.status == "draft"
    if slot.is_locked and not _approved:
        from .change_workflow import request_task_change
        if titles is not None:
            validate_subtask_change(task, titles)
        return request_task_change(plan, slot, task if task.pk else None, user, values, publish)
    task._definition_approved = _approved
    before = task_snapshot(task) if task.pk else {}
    if titles is not None:
        update_subtasks(task, titles)
    for field in ("title", "overview", "requirements", "estimated_minutes", "priority", "order", "assign_all"):
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
    if not _importing and not task.assign_all:
        from accounts.services.users import require_distinguishable_users
        from django.contrib.auth import get_user_model

        newly_selected = selected - set(before.get("selected_competitors", []))
        scope = get_user_model().objects.filter(pk__in=plan.participants.filter(is_active=True).values("user_id"))
        require_distinguishable_users(scope, newly_selected)
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
    task = TrainingTask.objects.select_for_update(of=("self",)).select_related("schedule_slot__day__training_plan").get(pk=task.pk)
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
    task = TrainingTask.objects.select_for_update(of=("self",)).select_related("schedule_slot__day__training_plan").get(pk=task.pk)
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
    task = TrainingTask.objects.select_for_update(of=("self",)).select_related("schedule_slot__day__training_plan").get(pk=task.pk)
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
    require_rosters(plan)
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
    task = TrainingTask.objects.select_for_update(of=("self",)).select_related("schedule_slot__day__training_plan").get(pk=task.pk)
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
    for execution in task.executions.select_for_update(of=("self",)).filter(status="assigned", started_at__isnull=True, progress_records__isnull=True):
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
