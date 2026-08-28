from __future__ import annotations

from django.db.models import Prefetch

from .models import ConductSeverityRule
from .permissions import (
    can_record_conduct,
    can_view_all_conduct_records,
)


def with_conduct_rule_data(queryset):
    return queryset.select_related('severity').prefetch_related(
        Prefetch(
            'severity__rules',
            queryset=ConductSeverityRule.objects.only(
                'nature',
                'severity_id',
                'label',
                'multiplier',
            ),
            to_attr='_conduct_rules',
        )
    )


def get_conduct_record_list_queryset(queryset, user):
    queryset = with_conduct_rule_data(queryset)
    if can_view_all_conduct_records(user):
        return queryset
    return queryset.filter(student=user)


def get_conduct_summary_list_queryset(queryset, user):
    if can_view_all_conduct_records(user):
        return queryset
    return queryset.filter(student=user)


def get_conduct_record_admin_queryset(queryset, user):
    queryset = with_conduct_rule_data(queryset)
    if can_view_all_conduct_records(user):
        return queryset

    if can_record_conduct(user):
        return queryset.filter(recorded_by=user)

    return queryset.none()
