from collections import Counter, defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Count, F, OuterRef, Prefetch, Q, Subquery

from accounts.services.users import get_user_display_name

from .models import TaskExecution, TrainingScheduleDay, TrainingScheduleSlot, TrainingTask, TrainingTaskDomain
from .scheduling import ACTIVE_KINDS


def _percentage(count, total):
    return (200 * count + total) // (2 * total)


def _coach_names(coaches, all_coaches):
    return ["全体"] if all_coaches else [get_user_display_name(coach) for coach in coaches.all()]


def _slot_display(period, label, slot, now, tasks):
    kind = TrainingScheduleSlot.Kind
    start, end = (slot.starts_at, slot.ends_at) if slot else (None, None)
    state, state_label = "unknown", "时间未设置"
    if start and end:
        if end <= now:
            state, state_label = "completed", "已结束"
        elif start <= now:
            state, state_label = "active", "进行中"
        else:
            state, state_label = "upcoming", "未开始"
    empty_label = "暂无任务"
    domains, coaches = [], []
    if not slot or not slot.is_configured or slot.kind == kind.UNUSED:
        empty_label = "不安排"
    elif slot.kind == kind.REST:
        empty_label = "休息"
    else:
        domains = [domain.name for domain in slot.domains.all()]
        if not domains and slot.primary_domain:
            domains = [slot.primary_domain.name]
        if not domains and slot.kind in {kind.GENERAL, kind.COMPREHENSIVE}:
            domains = [slot.get_kind_display()]
        coaches = _coach_names(slot.coaches, slot.coaches_all)
    return {
        "period": period, "label": label, "start": start, "end": end, "state": state,
        "state_label": state_label, "empty_label": empty_label, "domains": domains,
        "coaches": coaches, "tasks": tasks,
    }


def _statistics(tasks, slots):
    domains = Counter()
    counts = Counter()
    for task in tasks:
        slot = slots[task["schedule_slot_id"]]
        domain = task["primary_domain_name"] or (slot.primary_domain.name if slot.primary_domain else "其他")
        domains[domain] += 1
        for name in ("execution_total", "completed", "in_progress", "assigned"):
            counts[name] += task[name]

    total = counts["execution_total"]
    task_total = len(tasks)
    distribution = []
    offset = 0
    palette = (201, 184, 267, 42, 150, 323, 224, 21)
    for index, (name, count) in enumerate(sorted(domains.items())):
        end = offset + count
        distribution.append({
            "name": name, "count": count, "percent": _percentage(count, task_total),
            "hue": palette[index % len(palette)],
            "start": 10000 * offset // task_total, "end": 10000 * end // task_total,
        })
        offset = end
    return {
        **counts, "task_total": task_total, "execution_total": total,
        "other": total - counts["completed"] - counts["in_progress"] - counts["assigned"],
        "completion_rate": _percentage(counts["completed"], total) if total else None,
        "distribution": distribution,
    }


def public_board_plans(*, today, now):
    """只返回获准上屏的当天安排和匿名执行计数。"""
    coach_names = get_user_model().objects.only("first_name", "last_name").order_by("last_name", "first_name", "pk")
    slots = TrainingScheduleSlot.objects.select_related("primary_domain").prefetch_related(
        "domains", Prefetch("coaches", queryset=coach_names),
    )
    days = TrainingScheduleDay.objects.filter(
        date=today,
        training_plan__screen_listing__isnull=False,
        training_plan__published_at__isnull=False,
        training_plan__schedule_published_at__isnull=False,
        training_plan__start_date__lte=today,
        training_plan__end_date__gte=today,
    )
    schedule = list(days.select_related("training_plan").only(
        "training_plan__title", "duty_all",
    ).prefetch_related(
        Prefetch("duty_coaches", queryset=coach_names), Prefetch("slots", queryset=slots),
    ).order_by("training_plan__title", "training_plan_id"))
    if not schedule:
        return []

    tasks_by_slot = defaultdict(list)
    tasks_by_plan = defaultdict(list)
    status = TaskExecution.Status
    effective = Q(executions__revoked_at__isnull=True) & ~Q(executions__status=status.CANCELLED)
    primary_domain = TrainingTaskDomain.objects.filter(
        training_task_id=OuterRef("pk"), role=TrainingTaskDomain.Role.PRIMARY,
    ).values("technical_domain__name")
    tasks = TrainingTask.objects.filter(
        status=TrainingTask.Status.PUBLISHED,
        planned_date=today,
        schedule_slot__day__in=days.filter(pk__in=[day.pk for day in schedule]),
        schedule_slot__day__training_plan_id=F("training_plan_id"),
        schedule_slot__is_configured=True,
        schedule_slot__kind__in=ACTIVE_KINDS,
    ).values("pk", "title", "training_plan_id", "schedule_slot_id").annotate(
        primary_domain_name=Subquery(primary_domain[:1]),
        execution_total=Count("executions", filter=effective),
        completed=Count("executions", filter=effective & Q(executions__status=status.COMPLETED)),
        in_progress=Count("executions", filter=effective & Q(executions__status=status.IN_PROGRESS)),
        assigned=Count("executions", filter=effective & Q(executions__status=status.ASSIGNED)),
    ).order_by("order", "pk")
    slots_by_id = {slot.pk: slot for day in schedule for slot in day.slots.all()}
    for task in tasks:
        if task["schedule_slot_id"] in slots_by_id:
            tasks_by_slot[task["schedule_slot_id"]].append(task["title"])
            tasks_by_plan[task["training_plan_id"]].append(task)

    plans = []
    for day in schedule:
        by_period = {slot.period: slot for slot in day.slots.all()}
        display_slots = []
        for period, label in TrainingScheduleSlot.Period.choices:
            slot = by_period.get(period)
            display_slots.append(_slot_display(period, label, slot, now, tasks_by_slot[slot.pk] if slot else []))
        plans.append({
            "id": day.training_plan_id, "title": day.training_plan.title,
            "duty_coaches": _coach_names(day.duty_coaches, day.duty_all),
            "slots": display_slots, "statistics": _statistics(tasks_by_plan[day.training_plan_id], slots_by_id),
        })
    return plans
