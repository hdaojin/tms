from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import KnowledgeEvidence


def create_evidence_from_scoring_aspect(aspect, created_by=None):
    source_type = KnowledgeEvidence.SourceType.SCORING_ASPECT
    content_type = ContentType.objects.get_for_model(aspect)
    evidence, _created = KnowledgeEvidence.objects.update_or_create(
        source_content_type=content_type,
        source_object_id=aspect.pk,
        defaults={
            "skill_project": aspect.scheme.event_module.event.skill_project,
            "event_module": aspect.scheme.event_module,
            "title": aspect.description[:200],
            "original_text": aspect.description,
            "normalized_text": aspect.requirement or aspect.description,
            "estimated_mark": aspect.max_mark,
            "source_type": source_type,
            "extraction_source": KnowledgeEvidence.ExtractionSource.PARSER,
            "confidence": 1.0,
            "review_status": KnowledgeEvidence.ReviewStatus.APPROVED,
            "reviewed_by": created_by,
            "reviewed_at": timezone.now(),
            "created_by": created_by,
        },
    )
    return evidence


def create_evidence_from_exam_requirement(requirement, created_by=None):
    content_type = ContentType.objects.get_for_model(requirement)
    review_status = KnowledgeEvidence.ReviewStatus.APPROVED
    extraction_source = KnowledgeEvidence.ExtractionSource.MANUAL
    if requirement.extraction_source != requirement.ExtractionSource.MANUAL:
        review_status = KnowledgeEvidence.ReviewStatus.PENDING
        extraction_source = KnowledgeEvidence.ExtractionSource.PARSER

    evidence, _created = KnowledgeEvidence.objects.update_or_create(
        source_content_type=content_type,
        source_object_id=requirement.pk,
        defaults={
            "skill_project": requirement.paper.event_module.event.skill_project,
            "event_module": requirement.paper.event_module,
            "capability_domain": requirement.capability_domain,
            "title": requirement.title,
            "original_text": requirement.original_text,
            "normalized_text": requirement.normalized_text or requirement.original_text,
            "estimated_difficulty": requirement.estimated_difficulty,
            "source_type": KnowledgeEvidence.SourceType.EXAM_REQUIREMENT,
            "extraction_source": extraction_source,
            "confidence": 1.0,
            "review_status": review_status,
            "reviewed_by": created_by if review_status == KnowledgeEvidence.ReviewStatus.APPROVED else None,
            "reviewed_at": timezone.now() if review_status == KnowledgeEvidence.ReviewStatus.APPROVED else None,
            "created_by": created_by,
        },
    )
    return evidence
