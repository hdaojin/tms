from __future__ import annotations

from core.constants import GROUP_COACH, GROUP_COMPETITOR


VIEW_ALL_TRAININGLOG_PERMISSION = "traininglogs.view_all_traininglog"
VIEW_COACH_TRAININGLOG_PERMISSION = "traininglogs.view_coach_traininglog"
VIEW_COMPETITOR_TRAININGLOG_PERMISSION = "traininglogs.view_competitor_traininglog"


def get_user_group_names(user) -> set[str]:
    if not user or not getattr(user, "pk", None):
        return set()
    groups = getattr(user, "groups", None)
    if groups is None:
        return set()
    return set(groups.values_list("name", flat=True))


def can_view_all_traininglogs(user) -> bool:
    return getattr(user, "is_authenticated", False) and (
        getattr(user, "is_superuser", False)
        or user.has_perm(VIEW_ALL_TRAININGLOG_PERMISSION)
    )


def can_view_coach_traininglogs(user) -> bool:
    return getattr(user, "is_authenticated", False) and (
        can_view_all_traininglogs(user)
        or user.has_perm(VIEW_COACH_TRAININGLOG_PERMISSION)
    )


def can_view_competitor_traininglogs(user) -> bool:
    return getattr(user, "is_authenticated", False) and (
        can_view_all_traininglogs(user)
        or user.has_perm(VIEW_COMPETITOR_TRAININGLOG_PERMISSION)
    )


def _can_view_uploaded_user_logs(user, uploaded_user) -> bool:
    owner_groups = get_user_group_names(uploaded_user)
    if GROUP_COACH in owner_groups:
        return can_view_coach_traininglogs(user)
    if GROUP_COMPETITOR in owner_groups:
        return can_view_competitor_traininglogs(user)
    return False


def can_access_traininglog(user, traininglog) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if can_view_all_traininglogs(user):
        return True
    if getattr(traininglog, "uploaded_by_id", None) == getattr(user, "pk", None):
        return True

    owner_user = getattr(traininglog, "uploaded_by", None)
    return _can_view_uploaded_user_logs(user, owner_user)


def can_access_traininglog_request(request, traininglog) -> bool:
    return can_access_traininglog(getattr(request, "user", None), traininglog)


def can_view_cross_group_traininglog_list(user, uploaded_group_name: str) -> bool:
    if uploaded_group_name == GROUP_COACH:
        return can_view_coach_traininglogs(user)
    if uploaded_group_name == GROUP_COMPETITOR:
        return can_view_competitor_traininglogs(user)
    return can_view_all_traininglogs(user)