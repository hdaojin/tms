from __future__ import annotations

from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from accounts.services.users import annotate_identity_labels, get_user_display_name, user_name_search_ids
from standards.selectors import scoped_domains_for

from .models import TaskExecution, TrainingLog, TrainingPlan, TrainingScheduleSlot, TrainingTask


CLOSED_LOG_PLAN_STATUSES = (TrainingPlan.Status.COMPLETED, TrainingPlan.Status.ARCHIVED)


def log_reporting_plans(today):
    return TrainingPlan.objects.filter(
        published_at__isnull=False, schedule_published_at__isnull=False, start_date__lte=today,
    )


def ongoing_log_plans(today):
    return Q(end_date__gte=today) & ~Q(status__in=CLOSED_LOG_PLAN_STATUSES)


def log_plan_is_ongoing(plan, today):
    return plan.end_date >= today and plan.status not in CLOSED_LOG_PLAN_STATUSES


def log_plan_choices(plans, today):
    return [
        (plan.pk, f"{plan.title}（{'进行中' if log_plan_is_ongoing(plan, today) else '已完成'}，{plan.start_date:%Y-%m-%d}）")
        for plan in plans
    ]


def _log_plan_participation(user, plans):
    from .scheduling import ACTIVE_KINDS

    participant = plans.filter(pk=OuterRef("pk"), participants__user=user)
    coach = TrainingScheduleSlot.objects.filter(
        day__training_plan_id=OuterRef("pk"), coaches=user, is_configured=True, kind__in=ACTIVE_KINDS,
    ).exclude(period=TrainingScheduleSlot.Period.EARLY)
    return Exists(participant) | Exists(coach)


def training_log_statistics_plans_for(user):
    if not user.has_perm("training.view_traininglog_statistics"):
        return TrainingPlan.objects.none()
    plans = log_reporting_plans(timezone.localdate()).select_related("training_cycle")
    if user.has_perm("training.view_all_traininglog"):
        return plans
    return plans.filter(_log_plan_participation(user, plans))


def training_log_list_plans_for(user, today):
    if not user.has_perm("training.view_traininglog"):
        return TrainingPlan.objects.none()
    plans = log_reporting_plans(today)
    if user.has_perm("training.view_all_traininglog"):
        return plans
    own_logs = TrainingLog.objects.filter(
        author=user, training_cycle_id=OuterRef("training_cycle_id"),
        training_date__range=(OuterRef("start_date"), OuterRef("end_date")),
    )
    return plans.filter(_log_plan_participation(user, plans) | Exists(own_logs))


def _daily_competitors(plan, dates, *, include_backfill=True):
    """按变更当天的最后一份名单统计，缺少完整记录时保留可核实的分配。"""
    participants = list(plan.participants.values_list("user_id", "is_active", "was_initial"))
    current = {pk for pk, active, _ in participants if active}
    initial = {pk for pk, _, was_initial in participants if was_initial}
    records = [
        (timezone.localdate(created), before.get("参与选手"), set(after["参与选手"]))
        for created, before, after in plan.change_records.filter(
            after__has_key="参与选手",
        ).order_by("created_at", "pk").values_list("created_at", "before", "after")
    ]
    if records:
        # 首份变更前的完整名单只在有创建快照时有明确起点。
        known_initial = initial & set(records[0][1] if records[0][1] is not None else records[0][2])
    else:
        known_initial = initial & current

    rosters = {}
    index = 0
    roster = known_initial
    for day in dates:
        while index < len(records) and records[index][0] <= day:
            roster = records[index][2]
            index += 1
        next_before = records[index][1] if index < len(records) else current
        complete = index > 0 and next_before is not None and roster == set(next_before)
        # 有断档时，旧快照里的名单不能用来判断该日缺交。
        rosters[day] = (roster if complete or index == 0 else set(), complete)

    if not include_backfill:
        return rosters

    if any(not complete for _, complete in rosters.values()):
        from .historical_rosters import confirmed_rosters

        for day, roster in confirmed_rosters(plan).items():
            if day in rosters and not rosters[day][1]:
                rosters[day] = (roster, True)

    incomplete_days = [day for day, (_, complete) in rosters.items() if not complete]
    if incomplete_days:
        assignments = TaskExecution.objects.filter(
            training_task__training_plan=plan,
            training_task__status=TrainingTask.Status.PUBLISHED,
            training_task__schedule_slot__day__date__in=incomplete_days,
        ).exclude(training_task__schedule_slot__period=TrainingScheduleSlot.Period.EARLY).exclude(
            status=TaskExecution.Status.CANCELLED,
        ).values_list(
            "training_task__schedule_slot__day__date", "user_id", "revoked_at",
        )
        assigned = defaultdict(set)
        for day, user_id, revoked in assignments:
            if revoked is None or timezone.localdate(revoked) > day:
                assigned[day].add(user_id)
        for day in incomplete_days:
            rosters[day] = (rosters[day][0] | assigned[day], False)
    return rosters


def training_log_stat_slots(plan, start, end):
    from .scheduling import ACTIVE_KINDS

    return TrainingScheduleSlot.objects.filter(
        day__training_plan=plan, day__date__range=(start, end), kind__in=ACTIVE_KINDS, is_configured=True,
    ).exclude(period=TrainingScheduleSlot.Period.EARLY)


def training_log_daily_rosters(plan, start, end):
    slots = training_log_stat_slots(plan, start, end).values_list("day__date", "coaches_all", "coaches")
    coaches = defaultdict(set)
    named_coaches = defaultdict(set)
    for day, coaches_all, coach in slots:
        day_coaches = coaches[day]
        if coach is not None:
            day_coaches.add(coach)
            if not coaches_all:
                named_coaches[day].add(coach)
    coaches = dict(sorted(coaches.items()))
    competitors = _daily_competitors(plan, coaches) if coaches else {}
    return coaches, named_coaches, competitors


def training_log_submission_statistics(user, *, plan, q="", date_from=None, date_to=None):
    from .log_exemptions import exempt_users, exemption_history, exemption_rules

    if not training_log_statistics_plans_for(user).filter(pk=plan.pk).exists():
        return {}
    start = max(plan.start_date, date_from or plan.start_date)
    end = min(plan.end_date, date_to or plan.end_date, timezone.localdate())
    coaches, named_coaches, competitors = training_log_daily_rosters(plan, start, end)
    dates = list(coaches)
    exemptions = exempt_users(exemption_rules(exemption_history(plan)), dates) if dates else {}
    user_ids = set()
    for day in dates:
        user_ids.update(coaches[day], competitors[day][0])
    if not (user.is_superuser or user.has_perm("training.view_all_traininglog")):
        user_ids.intersection_update({user.pk})

    users = get_user_model().objects.filter(pk__in=user_ids)
    if q:
        users = users.filter(pk__in=user_name_search_ids(users, q))
    people = {
        person.pk: {"name": get_user_display_name(person), "count": 0, "expected": 0, "user_id": person.pk}
        for person in annotate_identity_labels(users)
    }
    logs = {
        (day, pk): log_id
        for day, pk, log_id in training_logs_visible_to(user).filter(
            training_cycle_id=plan.training_cycle_id, training_date__in=dates, author_id__in=people,
        ).values_list("training_date", "author_id", "pk")
    }
    possible_competitors = set()
    if people and any(not complete for _, complete in competitors.values()):
        from .historical_rosters import historical_candidates

        possible_competitors.update(historical_candidates(plan).filter(pk__in=people).values_list("pk", flat=True))
        for roster, _ in competitors.values():
            possible_competitors.update(roster & people.keys())
    uncertain = set()
    rows = []
    for day in dates:
        roster, complete = competitors[day]
        daily_competitors = roster & people.keys()
        daily_coaches = coaches[day] & people.keys()
        daily_named_coaches = named_coaches[day] & people.keys()
        exempt = exemptions[day]
        submitted = {
            pk: {"name": people[pk]["name"], "log_id": logs[day, pk]}
            for pk in daily_competitors | daily_coaches
            if (day, pk) in logs
        }
        for eligible, required in ((daily_competitors, daily_competitors), (daily_coaches, daily_named_coaches)):
            for pk in required - exempt:
                people[pk]["expected"] += 1
            for pk in eligible & submitted.keys():
                people[pk]["count"] += 1
        if not complete:
            uncertain.update(possible_competitors - daily_competitors - exemptions[day])
        missing_competitors = sorted(
            (people[pk]["name"], pk) for pk in daily_competitors - submitted.keys() - exempt
        ) if complete else []
        missing_coaches = sorted((people[pk]["name"], pk) for pk in daily_named_coaches - submitted.keys() - exempt)
        rows.append({
            "date": day,
            "submitted_competitors": sorted((submitted[pk] for pk in roster & submitted.keys()), key=lambda p: p["name"]),
            "submitted_coaches": sorted((submitted[pk] for pk in coaches[day] & submitted.keys()), key=lambda p: p["name"]),
            "unsubmitted_competitors": [name for name, _ in missing_competitors],
            "unsubmitted_coaches": [name for name, _ in missing_coaches],
            "own_missing_competitor": next((i for i, (_, pk) in enumerate(missing_competitors) if pk == user.pk), None),
            "own_missing_coach": next((i for i, (_, pk) in enumerate(missing_coaches) if pk == user.pk), None),
            "exempt_competitors": sorted(people[pk]["name"] for pk in daily_competitors & exempt),
            "exempt_coaches": sorted(people[pk]["name"] for pk in daily_named_coaches & exempt),
            "roster_complete": complete,
        })
    for pk in uncertain:
        people[pk]["expected"] = None
    ranked = sorted(people.values(), key=lambda p: (-p["count"], p["name"], p["user_id"]))
    return {"rows": rows, "people": ranked, "chart_max": max(1, ranked[0]["count"]) if ranked else 1}


def visible_training_tasks_for(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingTask.objects.all()
    if not user.is_authenticated or not user.has_perm("training.view_trainingtask"):
        return queryset.none()
    if user.is_superuser:
        return queryset
    from .scheduling import visible_plans
    active_assignment = TaskExecution.objects.filter(training_task_id=OuterRef("pk"), user=user, revoked_at__isnull=True).exclude(status="cancelled")
    queryset = queryset.annotate(_assigned_to_viewer=Exists(active_assignment))
    scheduled = Q(schedule_slot__isnull=False, training_plan__in=visible_plans(user)) & (
        Q(status="published", _assigned_to_viewer=True, training_plan__published_at__isnull=False, training_plan__schedule_published_at__isnull=False) | Q(schedule_slot__coaches=user)
        | Q(training_plan__schedulers=user) | Q(training_plan__approvers=user)
        | Q(training_plan__created_by=user)
    )
    domains = scoped_domains_for(user, "training.view_trainingtask")
    return queryset.filter(
        scheduled | (Q(schedule_slot__isnull=True) & (Q(executions__user=user) | Q(coach_links__user=user) | Q(domain_links__technical_domain__in=domains) | Q(training_plan__schedulers=user)))
    ).distinct()


def manageable_training_tasks_for(user, queryset=None):
    from .scheduling import ACTIVE_KINDS
    queryset = queryset if queryset is not None else TrainingTask.objects.all()
    if not user.has_perm("training.change_trainingtask"):
        return queryset.none()
    if user.is_superuser:
        return queryset.exclude(status="cancelled")
    role = Q(schedule_slot__coaches=user)
    if user.has_perm("training.schedule_trainingplan"):
        role |= Q(training_plan__schedulers=user)
    scheduled = queryset.filter(role, schedule_slot__isnull=False,
                                schedule_slot__kind__in=ACTIVE_KINDS).exclude(status="cancelled")
    queryset = queryset.filter(schedule_slot__isnull=True)
    domains = scoped_domains_for(user, "training.change_trainingtask")
    single_domain = queryset.annotate(domain_count=Count("domain_links", distinct=True)).filter(
        domain_count=1,
        domain_links__technical_domain__in=domains,
    )
    explicit = queryset.filter(coach_links__user=user)
    return (single_domain | explicit | scheduled).distinct()


def visible_task_executions_for(user, queryset=None):
    queryset = queryset if queryset is not None else TaskExecution.objects.all()
    if user.is_superuser:
        return queryset
    return queryset.filter(
        Q(user=user, training_task__schedule_slot__isnull=True)
        | (Q(user=user, training_task__status="published", revoked_at__isnull=True, training_task__training_plan__published_at__isnull=False, training_task__training_plan__schedule_published_at__isnull=False) & ~Q(status="cancelled"))
        | Q(training_task__coach_links__user=user)
    ).distinct()


def training_logs_visible_to(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    if user.has_perm("training.view_all_traininglog") or user.is_superuser:
        return queryset
    return queryset.filter(author=user)


def training_logs_changeable_by(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    queryset = queryset.filter(online_document={})
    if user.has_perm("training.change_all_traininglog") or user.is_superuser:
        return queryset
    return queryset.filter(author=user)


def training_logs_deletable_by(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    if not user.has_perms(("training.view_traininglog", "training.delete_traininglog")):
        return queryset.none()
    if user.is_superuser:
        return queryset
    if not user.has_perm("training.delete_all_traininglog"):
        queryset = queryset.filter(author=user)
    today = timezone.localdate()
    matches_log = Q(
        training_cycle_id=OuterRef("training_cycle_id"),
        start_date__lte=OuterRef("training_date"), end_date__gte=OuterRef("training_date"),
    )
    ongoing = ongoing_log_plans(today)
    current = log_reporting_plans(today).filter(matches_log, ongoing)
    historical = TrainingPlan.objects.filter(
        matches_log, Q(published_at__isnull=False) | Q(status__in=CLOSED_LOG_PLAN_STATUSES),
    ).exclude(ongoing)
    return training_logs_visible_to(user, queryset).filter(
        Exists(current), ~Exists(historical), training_date__lte=today,
    )
