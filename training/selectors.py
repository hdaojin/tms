from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from accounts.services.users import get_user_display_name
from standards.selectors import scoped_domains_for

from .models import TaskExecution, TrainingCycle, TrainingCycleMember, TrainingLog, TrainingTask


def training_log_statistics_cycles_for(user):
    if not user.has_perm("training.view_traininglog_statistics"):
        return TrainingCycle.objects.none()
    cycles = TrainingCycle.objects.select_related("skill_project")
    if user.is_superuser or user.has_perm("training.view_all_traininglog"):
        return cycles
    return cycles.filter(members__user=user)


def training_log_submission_statistics(user, *, cycle, year, month, role=""):
    """以周期现有成员为对照，汇总训练日期上的提交事实。"""
    empty = {"rows": [], "people": [], "range_start": None, "range_end": None}
    if not training_log_statistics_cycles_for(user).filter(pk=cycle.pk).exists():
        return empty
    start = max(date(year, month, 1), cycle.start_date)
    end = min(date(year, month, monthrange(year, month)[1]), timezone.localdate())
    if cycle.end_date:
        end = min(end, cycle.end_date)
    if start > end:
        return empty
    members = TrainingCycleMember.objects.filter(training_cycle=cycle).select_related("user")
    if not (user.is_superuser or user.has_perm("training.view_all_traininglog")):
        members = members.filter(user=user)
    if role:
        members = members.filter(role=role)
    people = sorted(
        ({"user_id": member.user_id, "name": get_user_display_name(member.user),
          "role": member.get_role_display(), "count": 0} for member in members),
        key=lambda person: (person["name"], person["user_id"]),
    )
    logs = training_logs_visible_to(user).filter(
        training_cycle=cycle, training_date__range=(start, end),
        author_id__in=[person["user_id"] for person in people],
    ).values_list("training_date", "author_id", "pk")
    by_day = {}
    for day, author_id, pk in logs:
        by_day.setdefault(day, {})[author_id] = pk
    rows = []
    day = start
    while day <= end:
        submitted, unsubmitted = [], []
        for person in people:
            log_id = by_day.get(day, {}).get(person["user_id"])
            if log_id is not None:
                submitted.append({"name": person["name"], "log_id": log_id})
                person["count"] += 1
            else:
                unsubmitted.append(person["name"])
        rows.append({"date": day, "submitted": submitted, "unsubmitted": unsubmitted})
        day += timedelta(days=1)
    return {"rows": rows, "people": people, "range_start": start, "range_end": end}


def visible_training_tasks_for(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingTask.objects.all()
    if not user.is_authenticated or not user.has_perm("training.view_trainingtask"):
        return queryset.none()
    if user.is_superuser:
        return queryset
    domains = scoped_domains_for(user, "training.view_trainingtask")
    return queryset.filter(
        Q(executions__user=user) | Q(coach_links__user=user) | Q(domain_links__technical_domain__in=domains)
    ).distinct()


def manageable_training_tasks_for(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingTask.objects.all()
    if not user.has_perm("training.change_trainingtask"):
        return queryset.none()
    if user.is_superuser:
        return queryset
    domains = scoped_domains_for(user, "training.change_trainingtask")
    single_domain = queryset.annotate(domain_count=Count("domain_links", distinct=True)).filter(
        domain_count=1,
        domain_links__technical_domain__in=domains,
    )
    explicit = queryset.filter(coach_links__user=user)
    return (single_domain | explicit).distinct()


def visible_task_executions_for(user, queryset=None):
    queryset = queryset if queryset is not None else TaskExecution.objects.all()
    if user.is_superuser:
        return queryset
    return queryset.filter(Q(user=user) | Q(training_task__coach_links__user=user)).distinct()


def training_logs_visible_to(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    if user.has_perm("training.view_all_traininglog") or user.is_superuser:
        return queryset
    return queryset.filter(author=user)


def training_logs_changeable_by(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    if user.has_perm("training.change_all_traininglog") or user.is_superuser:
        return queryset
    return queryset.filter(author=user)


def training_logs_deletable_by(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    if not user.has_perm("training.delete_traininglog"):
        return queryset.none()
    if user.has_perm("training.delete_all_traininglog") or user.is_superuser:
        return queryset
    return queryset.filter(author=user)
