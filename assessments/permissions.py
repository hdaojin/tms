from __future__ import annotations

from core.constants import GROUP_COACH

from .models import AssessmentModule


def is_coach(user) -> bool:
    return getattr(user, "is_authenticated", False) and user.groups.filter(name=GROUP_COACH).exists()


def is_superuser(user) -> bool:
    return getattr(user, "is_authenticated", False) and getattr(user, "is_superuser", False)


def get_managed_modules_queryset(user, assessment=None):
    queryset = AssessmentModule.objects.select_related(
        "assessment", "module", "responsible_coach"
    )
    if assessment is not None:
        queryset = queryset.filter(assessment=assessment)
    if not is_coach(user):
        return queryset.none()
    return queryset.filter(responsible_coach=user).order_by(
        "sort_order", "module__code", "pk"
    )


def can_access_assessment_detail(user, assessment) -> bool:
    return (
        getattr(user, "is_superuser", False)
        or user.has_perm("assessments.view_all_scores")
        or get_managed_modules_queryset(user, assessment).exists()
    )


def can_manage_assessment_module(user, assessment_module) -> bool:
    return is_coach(user) and assessment_module.responsible_coach_id == user.id


def can_lock_assessment_module(user, assessment_module) -> bool:
    return is_superuser(user) or can_manage_assessment_module(user, assessment_module)


def can_unlock_assessment_module(user) -> bool:
    return is_superuser(user)