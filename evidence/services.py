from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from assessments.models import AssessmentDocument

from .models import EvidenceSkillMap, KnowledgeEvidence


@transaction.atomic
def create_evidence_from_scoring_aspect(aspect, created_by=None):
    document = aspect.scheme.source_document
    evidence, _ = KnowledgeEvidence.objects.update_or_create(
        scoring_aspect=aspect,
        defaults={
            "skill_project": aspect.scheme.assessment_module.assessment.skill_project,
            "assessment_module": aspect.scheme.assessment_module,
            "source_document": document,
            "source_type": KnowledgeEvidence.SourceType.SCORING_ASPECT,
            "title": aspect.description[:200],
            "original_text": aspect.description,
            "normalized_text": aspect.requirement or aspect.description,
            "estimated_mark": aspect.max_mark,
            "extraction_source": KnowledgeEvidence.ExtractionSource.PARSER,
            "confidence": 1.0,
            "review_status": KnowledgeEvidence.ReviewStatus.APPROVED,
            "reviewed_by": created_by,
            "reviewed_at": timezone.now(),
            "created_by": created_by,
        },
    )
    return evidence


@transaction.atomic
def create_manual_evidence_from_document(document, *, title, created_by=None, **values):
    source_type = values.pop("source_type", None)
    if source_type is None:
        source_type = (
            KnowledgeEvidence.SourceType.TEST_PROJECT
            if document.document_type == AssessmentDocument.DocumentType.TEST_PROJECT
            else KnowledgeEvidence.SourceType.MANUAL
        )
    return KnowledgeEvidence.objects.create(
        skill_project=document.assessment.skill_project,
        assessment_module=document.module,
        source_document=document,
        source_type=source_type,
        title=title,
        extraction_source=KnowledgeEvidence.ExtractionSource.MANUAL,
        review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        reviewed_by=created_by,
        reviewed_at=timezone.now(),
        created_by=created_by,
        **values,
    )


def approve_evidence(evidence, user=None, note=""):
    evidence.approve(user=user, note=note)
    return evidence


def reject_evidence(evidence, user=None, note=""):
    evidence.reject(user=user, note=note)
    return evidence


@transaction.atomic
def approve_mapping(mapping, user=None):
    mapping = EvidenceSkillMap.objects.select_for_update().get(pk=mapping.pk)
    mapping.review_status = KnowledgeEvidence.ReviewStatus.APPROVED
    mapping.reviewed_by = user
    mapping.reviewed_at = timezone.now()
    mapping.save()
    return mapping
