from __future__ import annotations

from .permissions import (
    can_record_conduct,
    can_view_all_conduct_records,
)


def get_conduct_record_list_queryset(queryset, user):
    if can_view_all_conduct_records(user):
        return queryset
    return queryset.filter(student=user)


def get_conduct_summary_list_queryset(queryset, user):
    if can_view_all_conduct_records(user):
        return queryset
    return queryset.filter(student=user)


def get_conduct_record_admin_queryset(queryset, user):
    if can_view_all_conduct_records(user):
        return queryset

    if can_record_conduct(user):
        return queryset.filter(recorded_by=user)

    return queryset.none()