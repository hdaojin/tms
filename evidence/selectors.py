from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, DecimalField, Exists, ExpressionWrapper, F, Max, OuterRef, Q, Sum, Value
from django.db.models.functions import Coalesce

from assessments.selectors import assessment_modules_in_scope_for

from .models import EvidenceSkillMap, KnowledgeEvidence


APPROVED = KnowledgeEvidence.ReviewStatus.APPROVED


def visible_evidences_for(user, queryset=None):
    queryset = queryset if queryset is not None else KnowledgeEvidence.objects.all()
    if not user.is_authenticated or not user.has_perm("evidence.view_knowledgeevidence"):
        return queryset.none()
    if user.is_superuser or user.has_perm("assessments.view_all_assessment"):
        return queryset
    modules = assessment_modules_in_scope_for(user, "evidence.view_knowledgeevidence")
    return queryset.filter(
        Q(assessment_module__in=modules) | Q(assessment_module__isnull=True, created_by=user)
    ).distinct()


def approved_evidences():
    return KnowledgeEvidence.objects.filter(review_status=APPROVED)


def approved_mappings():
    return EvidenceSkillMap.objects.filter(
        review_status=APPROVED, evidence__review_status=APPROVED, skill__is_active=True
    )


def get_unmapped_evidences(skill_project=None):
    mapped = approved_mappings().filter(evidence_id=OuterRef("pk"))
    queryset = approved_evidences().annotate(has_mapping=Exists(mapped)).filter(has_mapping=False)
    if skill_project is not None:
        queryset = queryset.filter(skill_project=skill_project)
    return queryset.select_related("skill_project", "assessment_module", "source_document")


def get_skill_evidences(skill):
    return approved_evidences().filter(skill_mappings__skill=skill, skill_mappings__review_status=APPROVED).distinct()


def skill_history_summary(skill):
    mappings = approved_mappings().filter(skill=skill)
    weighted = ExpressionWrapper(
        Coalesce(
            F("evidence__estimated_mark"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=8, decimal_places=2),
        )
        * F("weight"),
        output_field=DecimalField(max_digits=12, decimal_places=4),
    )
    return mappings.aggregate(
        evidence_count=Count("evidence", distinct=True),
        assessment_count=Count("evidence__assessment_module__assessment", distinct=True),
        latest_date=Max("evidence__assessment_module__assessment__start_date"),
        weighted_mark=Coalesce(Sum(weighted), Decimal("0.0000")),
    )
