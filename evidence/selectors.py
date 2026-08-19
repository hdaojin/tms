from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, DecimalField, Exists, ExpressionWrapper, F, Max, OuterRef, Sum, Value
from django.db.models.functions import Coalesce

from .models import EvidenceSkillMap, KnowledgeEvidence


APPROVED = KnowledgeEvidence.ReviewStatus.APPROVED


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
