from __future__ import annotations

from django.db.models import Count, Q

from standards.selectors import is_project_admin, manageable_domains_for

from .models import TaskExecution, TrainingLog, TrainingTask


def visible_training_tasks_for(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingTask.objects.all()
    if is_project_admin(user):
        return queryset
    return queryset.filter(
        Q(executions__user=user) | Q(coach_links__user=user) | Q(domain_links__technical_domain__memberships__user=user)
    ).distinct()


def manageable_training_tasks_for(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingTask.objects.all()
    if not user.has_perm("training.change_trainingtask"):
        return queryset.none()
    if is_project_admin(user):
        return queryset
    domains = manageable_domains_for(user)
    single_domain = queryset.annotate(domain_count=Count("domain_links", distinct=True)).filter(
        domain_count=1,
        domain_links__technical_domain__in=domains,
    )
    explicit = queryset.filter(coach_links__user=user)
    return (single_domain | explicit).distinct()


def visible_task_executions_for(user, queryset=None):
    queryset = queryset if queryset is not None else TaskExecution.objects.all()
    if is_project_admin(user):
        return queryset
    return queryset.filter(Q(user=user) | Q(training_task__coach_links__user=user)).distinct()


def training_logs_visible_to(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    if user.has_perm("training.view_all_traininglog") or is_project_admin(user):
        return queryset
    return queryset.filter(author=user)


def training_logs_changeable_by(user, queryset=None):
    queryset = queryset if queryset is not None else TrainingLog.objects.all()
    if user.has_perm("training.change_all_traininglog") or is_project_admin(user):
        return queryset
    return queryset.filter(author=user)
