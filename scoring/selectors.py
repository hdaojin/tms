from decimal import Decimal

from django.db.models import Count, Q, Sum

from assessments.models import AssessmentDocument, AssessmentModule
from assessments.selectors import assessment_modules_in_scope_for

from .models import ScoringResult, ScoringScheme, ScoringSchemeImport


def scoring_modules_in_scope_for(user, permission: str, queryset=None):
    queryset = queryset if queryset is not None else AssessmentModule.objects.all()
    return assessment_modules_in_scope_for(user, permission, queryset)


def scoring_schemes_in_scope_for(user, permission="scoring.view_scoringscheme", queryset=None):
    queryset = queryset if queryset is not None else ScoringScheme.objects.all()
    module_ids = scoring_modules_in_scope_for(user, permission).values("pk")
    return queryset.filter(assessment_module_id__in=module_ids)


def scoring_scheme_imports_in_scope_for(user, permission="scoring.add_scoringscheme", queryset=None):
    queryset = queryset if queryset is not None else ScoringSchemeImport.objects.all()
    module_ids = scoring_modules_in_scope_for(user, permission).values("pk")
    return queryset.filter(assessment_module_id__in=module_ids)


def scoring_scheme_documents_in_scope_for(user, permission="scoring.add_scoringscheme", queryset=None):
    queryset = queryset if queryset is not None else AssessmentDocument.objects.all()
    module_ids = scoring_modules_in_scope_for(user, permission).values("pk")
    return queryset.filter(
        document_type=AssessmentDocument.DocumentType.MARKING_STANDARD,
        module_id__in=module_ids,
    )


def scoring_results_in_scope_for(user, permission: str, queryset=None):
    queryset = queryset if queryset is not None else ScoringResult.objects.all()
    module_ids = scoring_modules_in_scope_for(user, permission).values("pk")
    return queryset.filter(aspect__scheme__assessment_module_id__in=module_ids)


def scoring_results_visible_to(user, queryset=None):
    queryset = queryset if queryset is not None else ScoringResult.objects.all()
    if not user.is_authenticated or not user.has_perm("scoring.view_scoringresult"):
        return queryset.none()
    if user.is_superuser:
        return queryset
    if user.has_perm("scoring.view_all_scoringresult"):
        return scoring_results_in_scope_for(user, "scoring.view_scoringresult", queryset)
    return queryset.filter(participant__user=user)


def module_scoring_summary(module, scheme):
    return assessment_scoring_summaries(module.assessment, [scheme]).get(
        module.pk,
        _build_scoring_summary(0, 0, Decimal("0.00"), {}),
    )


def _build_scoring_summary(participant_count, aspect_count, max_per_participant, result_summary):
    scored_count = result_summary.get("scored_count") or 0
    expected_count = participant_count * aspect_count
    available_total = max_per_participant * participant_count
    score_total = result_summary.get("score_total") or Decimal("0.00")
    completion_percent = (
        (Decimal(scored_count) * Decimal("100") / Decimal(expected_count)).quantize(Decimal("0.1"))
        if expected_count
        else Decimal("0.0")
    )
    score_rate = (
        (score_total * Decimal("100") / available_total).quantize(Decimal("0.1"))
        if available_total
        else Decimal("0.0")
    )
    return {
        "participant_count": participant_count,
        "aspect_count": aspect_count,
        "expected_count": expected_count,
        "scored_count": scored_count,
        "unfinished_count": expected_count - scored_count,
        "confirmed_count": result_summary.get("confirmed_count") or 0,
        "scored_participant_count": result_summary.get("scored_participant_count") or 0,
        "score_total": score_total,
        "available_total": available_total,
        "completion_percent": completion_percent,
        "score_rate": score_rate,
    }


def assessment_scoring_summaries(assessment, schemes):
    schemes = list(schemes)
    if not schemes:
        return {}
    participant_count = assessment.participants.filter(role__category="competitor").count()
    scheme_ids = [scheme.pk for scheme in schemes]
    aspect_rows = {
        row["assessment_module_id"]: row
        for row in ScoringScheme.objects.filter(pk__in=scheme_ids)
        .values("assessment_module_id")
        .annotate(aspect_count=Count("aspects"), max_per_participant=Sum("aspects__max_mark"))
        .values("assessment_module_id", "aspect_count", "max_per_participant")
    }
    result_rows = {
        row["aspect__scheme__assessment_module_id"]: row
        for row in ScoringResult.objects.filter(
            participant__assessment=assessment,
            participant__role__category="competitor",
            aspect__scheme_id__in=scheme_ids,
        )
        .values("aspect__scheme__assessment_module_id")
        .annotate(
            scored_count=Count("pk"),
            confirmed_count=Count("pk", filter=Q(confirmed_at__isnull=False)),
            scored_participant_count=Count("participant_id", distinct=True),
            score_total=Sum("score_awarded"),
        )
    }
    summaries = {}
    for scheme in schemes:
        module_id = scheme.assessment_module_id
        aspect_row = aspect_rows.get(module_id, {})
        summaries[module_id] = _build_scoring_summary(
            participant_count,
            aspect_row.get("aspect_count") or 0,
            aspect_row.get("max_per_participant") or Decimal("0.00"),
            result_rows.get(module_id, {}),
        )
    return summaries
