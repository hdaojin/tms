from __future__ import annotations

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


GLOBAL_CATALOG_PERMISSION = 'behaviors.manage_global_conduct_catalog'


def can_manage_catalog(user):
    return user.is_active and user.has_perm(GLOBAL_CATALOG_PERMISSION)
