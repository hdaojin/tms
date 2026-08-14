from __future__ import annotations

from .models import ConductRecord


ADD_CONDUCT_RECORD_PERMISSION = "behaviors.add_conduct_record"
REVIEW_CONDUCT_RECORD_PERMISSION = "behaviors.review_conduct_record"
VIEW_ALL_CONDUCT_RECORDS_PERMISSION = "behaviors.view_all_conduct_records"
VIEW_CONDUCT_RECORD_PERMISSION = "behaviors.view_conductrecord"
CHANGE_CONDUCT_RECORD_PERMISSION = "behaviors.change_conductrecord"
DELETE_CONDUCT_RECORD_PERMISSION = "behaviors.delete_conductrecord"


def can_record_conduct(user) -> bool:
    return getattr(user, "is_authenticated", False) and (
        getattr(user, "is_superuser", False)
        or user.has_perm(ADD_CONDUCT_RECORD_PERMISSION)
    )


def can_review_conduct(user) -> bool:
    return getattr(user, "is_authenticated", False) and (
        getattr(user, "is_superuser", False)
        or user.has_perm(REVIEW_CONDUCT_RECORD_PERMISSION)
    )


def can_view_all_conduct_records(user) -> bool:
    return getattr(user, "is_authenticated", False) and (
        getattr(user, "is_superuser", False)
        or user.has_perm(VIEW_ALL_CONDUCT_RECORDS_PERMISSION)
        or can_review_conduct(user)
    )


def can_access_conduct_record_admin_module(user) -> bool:
    return (
        can_record_conduct(user)
        or can_review_conduct(user)
        or can_view_all_conduct_records(user)
        or user.has_perm(VIEW_CONDUCT_RECORD_PERMISSION)
        or user.has_perm(CHANGE_CONDUCT_RECORD_PERMISSION)
        or user.has_perm(DELETE_CONDUCT_RECORD_PERMISSION)
    )


def can_view_conduct_record_admin(user, obj=None) -> bool:
    if not can_access_conduct_record_admin_module(user):
        return False

    if obj is None or can_view_all_conduct_records(user):
        return True

    return can_record_conduct(user) and obj.recorded_by_id == user.id


def can_change_conduct_record_admin(user, obj=None) -> bool:
    if obj is None:
        return can_record_conduct(user) or can_review_conduct(user)

    if not can_view_conduct_record_admin(user, obj):
        return False

    if obj.status != ConductRecord.STATUS_PENDING:
        return False

    if can_review_conduct(user):
        return True

    return can_record_conduct(user) and obj.recorded_by_id == user.id
