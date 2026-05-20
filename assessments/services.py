from __future__ import annotations

from django.utils import timezone


def set_score_lock_state(assessment_module, *, is_locked, user=None):
    assessment_module.is_locked = is_locked
    assessment_module.locked_at = timezone.now() if is_locked else None
    assessment_module.locked_by = user if is_locked else None
    assessment_module.save(update_fields=["is_locked", "locked_at", "locked_by"])


def set_material_lock_state(assessment_module, *, is_locked, user=None):
    assessment_module.is_material_locked = is_locked
    assessment_module.material_locked_at = timezone.now() if is_locked else None
    assessment_module.material_locked_by = user if is_locked else None
    assessment_module.save(
        update_fields=[
            "is_material_locked",
            "material_locked_at",
            "material_locked_by",
        ]
    )