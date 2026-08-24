from decimal import Decimal

from django.db.models import Count, Q, Sum

from scoring.models import ScoringAspect, ScoringResult
from standards.selectors import scoped_domains_for

from .models import Assessment, AssessmentDocument, AssessmentFinalResult, AssessmentModule, AssessmentParticipant


def _project_wide_permission(permission: str) -> str:
    codename = permission.split(".", maxsplit=1)[-1]
    if codename.startswith("view_"):
        return "assessments.view_all_assessment"
    return "assessments.change_all_assessment"


def assessments_in_scope_for(user, permission: str, queryset=None, *, include_participant=False):
    queryset = queryset if queryset is not None else Assessment.objects.all()
    if not user.is_authenticated or not user.has_perm(permission):
        return queryset.none()
    if user.is_superuser or user.has_perm(_project_wide_permission(permission)):
        return queryset

    domain_ids = scoped_domains_for(user, permission).values("pk")
    scope = Q(created_by=user) | Q(modules__coach_assignments__user=user)
    scope |= Q(modules__domain_mappings__technical_domain_id__in=domain_ids)
    if include_participant:
        scope |= Q(participants__user=user)
    return queryset.filter(scope).distinct()


def visible_assessments_for(user, queryset=None):
    return assessments_in_scope_for(
        user,
        "assessments.view_assessment",
        queryset,
        include_participant=True,
    )


def manageable_assessments_for(user, queryset=None):
    queryset = queryset if queryset is not None else Assessment.objects.all()
    if not user.is_authenticated or not user.has_perm("assessments.change_assessment"):
        return queryset.none()
    if user.is_superuser or user.has_perm("assessments.change_all_assessment"):
        return queryset
    return queryset.filter(created_by=user)


def assessment_modules_in_scope_for(
    user,
    permission: str,
    queryset=None,
    *,
    include_participant=False,
):
    queryset = queryset if queryset is not None else AssessmentModule.objects.all()
    if not user.is_authenticated or not user.has_perm(permission):
        return queryset.none()
    if user.is_superuser or user.has_perm(_project_wide_permission(permission)):
        return queryset

    domain_ids = scoped_domains_for(user, permission).values("pk")
    single_domain = queryset.annotate(_domain_count=Count("domain_mappings", distinct=True)).filter(
        _domain_count=1,
        domain_mappings__technical_domain_id__in=domain_ids,
    )
    explicit_scope = Q(coach_assignments__user=user) | Q(assessment__created_by=user)
    if include_participant:
        explicit_scope |= Q(assessment__participants__user=user)
    return (single_domain | queryset.filter(explicit_scope)).distinct()


def visible_assessment_modules_for(user, queryset=None):
    return assessment_modules_in_scope_for(
        user,
        "assessments.view_assessmentmodule",
        queryset,
        include_participant=True,
    )


def manageable_assessment_modules_for(user, queryset=None):
    return assessment_modules_in_scope_for(
        user,
        "assessments.change_assessmentmodule",
        queryset,
    )


def can_manage_assessment_module(user, module):
    return manageable_assessment_modules_for(user).filter(pk=module.pk).exists()


def visible_assessment_participants_for(user, queryset=None):
    queryset = queryset if queryset is not None else AssessmentParticipant.objects.all()
    if not user.is_authenticated or not user.has_perm("assessments.view_assessmentparticipant"):
        return queryset.none()
    return queryset.filter(assessment_id__in=visible_assessments_for(user).values("pk"))


def participant_assessments_in_scope_for(user, permission: str, queryset=None):
    return assessments_in_scope_for(user, permission, queryset, include_participant=False)


def visible_documents_for(user, queryset=None):
    queryset = queryset if queryset is not None else AssessmentDocument.objects.all()
    if not user.is_authenticated or not user.has_perm("assessments.view_assessmentdocument"):
        return queryset.none()
    module_ids = assessment_modules_in_scope_for(
        user,
        "assessments.view_assessmentdocument",
        include_participant=True,
    ).values("pk")
    assessment_ids = visible_assessments_for(user).values("pk")
    return queryset.filter(
        Q(module_id__in=module_ids) | Q(module__isnull=True, assessment_id__in=assessment_ids)
    ).distinct()


def calculated_final_result_preview(assessment):
    participants = list(
        assessment.participants.filter(role__category="competitor").select_related("role").order_by("display_name", "pk")
    )
    aspects = ScoringAspect.objects.filter(
        scheme__assessment_module__assessment=assessment,
        scheme__assessment_module__counts_towards_ranking=True,
    )
    aspect_summary = aspects.aggregate(count=Count("pk"), max_total=Sum("max_mark"))
    aspect_count = aspect_summary["count"]
    max_total = aspect_summary["max_total"] or Decimal("0.00")
    result_rows = {
        row["participant_id"]: row
        for row in ScoringResult.objects.filter(
            participant__in=participants,
            aspect__in=aspects,
        )
        .values("participant_id")
        .annotate(score=Sum("score_awarded"), scored_count=Count("pk"))
    }
    preview = []
    for participant in participants:
        row = result_rows.get(participant.pk, {})
        score = row.get("score") or Decimal("0.00")
        percentage = (
            (score * Decimal("100") / max_total).quantize(Decimal("0.0001"))
            if max_total
            else None
        )
        preview.append(
            {
                "participant": participant,
                "raw_score": score,
                "max_score": max_total,
                "percentage": percentage,
                "scored_count": row.get("scored_count") or 0,
                "expected_count": aspect_count,
                "is_complete": (row.get("scored_count") or 0) == aspect_count and aspect_count > 0,
            }
        )
    preview.sort(key=lambda item: (-item["raw_score"], item["participant"].display_name, item["participant"].pk))
    previous_score = None
    previous_rank = None
    for position, item in enumerate(preview, start=1):
        if item["raw_score"] != previous_score:
            previous_rank = position
            previous_score = item["raw_score"]
        item["rank"] = previous_rank
    return preview


def visible_final_results_for(user, assessment, queryset=None):
    queryset = queryset if queryset is not None else AssessmentFinalResult.objects.all()
    queryset = queryset.filter(participant__assessment=assessment)
    if not user.is_authenticated or not user.has_perm("assessments.view_assessmentfinalresult"):
        return queryset.none()
    if user.is_superuser or user.has_perm("assessments.view_all_assessment") or assessment.created_by_id == user.pk:
        return queryset
    if assessment.results_published_at is None:
        return queryset.none()
    return queryset.filter(is_official=True, participant__user=user)


def manageable_final_results_for(user, queryset=None):
    queryset = queryset if queryset is not None else AssessmentFinalResult.objects.all()
    if not user.is_authenticated or not user.has_perm("assessments.change_assessmentfinalresult"):
        return queryset.none()
    assessment_ids = manageable_assessments_for(user).values("pk")
    return queryset.filter(participant__assessment_id__in=assessment_ids)
