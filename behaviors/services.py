from __future__ import annotations

from django.utils import timezone

from .models import ConductRecord


def prepare_conduct_record_for_save(record, *, actor, change, now=None):
    current_time = now or timezone.now()

    if not change:
        record.recorded_by = actor
        record.status = ConductRecord.STATUS_PENDING
        return record

    record.updated_by = actor
    original_status = ConductRecord.objects.filter(pk=record.pk).values_list("status", flat=True).first()
    if (
        original_status == ConductRecord.STATUS_PENDING
        and record.status in [ConductRecord.STATUS_APPROVED, ConductRecord.STATUS_REJECTED]
    ):
        record.reviewed_by = actor
        record.reviewed_at = current_time

    return record


def discard_conduct_summary_delete_permission(perms_needed):
    from .models import ConductSummary

    perms_needed.discard(ConductSummary._meta.verbose_name)
    return perms_needed