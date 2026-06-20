from __future__ import annotations

from knowledge.services import create_evidence_from_exam_requirement


def create_evidence_for_requirement(requirement, created_by=None):
    return create_evidence_from_exam_requirement(requirement, created_by=created_by)
