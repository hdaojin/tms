from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from .models import ConductNature

def _get_conduct_record_model():
    from .models import ConductRecord

    return ConductRecord


def _get_conduct_summary_model():
    from .models import ConductSummary

    return ConductSummary


def _get_conduct_severity_rule_model():
    from .models import ConductSeverityRule

    return ConductSeverityRule


def prepare_conduct_record_for_save(record, *, actor, change, now=None):
    current_time = now or timezone.now()
    record_model = type(record)

    if not change:
        record.recorded_by = actor
        record.status = record_model.Status.PENDING
        return record

    record.updated_by = actor
    original_status = record_model.objects.filter(pk=record.pk).values_list("status", flat=True).first()
    if (
        original_status == record_model.Status.PENDING
        and record.status in [record_model.Status.APPROVED, record_model.Status.REJECTED]
    ):
        record.reviewed_by = actor
        record.reviewed_at = current_time

    return record


def recalculate_conduct_summary(summary):
    conduct_record_model = _get_conduct_record_model()
    conduct_severity_rule_model = _get_conduct_severity_rule_model()

    approved_records = summary.student.conduct_records.filter(
        status=conduct_record_model.Status.APPROVED,
    ).select_related('item__category', 'severity')
    rule_map = {
        (rule.nature, rule.severity_id): rule.multiplier
        for rule in conduct_severity_rule_model.objects.all()
    }

    total_score = Decimal('0')
    reward_count = 0
    penalty_count = 0

    for record in approved_records:
        total_score += record.get_score(rule_map=rule_map)
        if record.item.category.nature == ConductNature.REWARD:
            reward_count += 1
        elif record.item.category.nature == ConductNature.PENALTY:
            penalty_count += 1

    summary.total_score = total_score
    summary.reward_count = reward_count
    summary.penalty_count = penalty_count
    summary.save()
    return summary


def refresh_conduct_summary(student_id):
    if student_id is None:
        return None

    conduct_summary_model = _get_conduct_summary_model()
    summary, _ = conduct_summary_model.objects.get_or_create(student_id=student_id)
    return recalculate_conduct_summary(summary)


def refresh_conduct_summaries(student_ids):
    refreshed_summaries = []
    for student_id in set(student_ids):
        if student_id is None:
            continue
        refreshed_summary = refresh_conduct_summary(student_id)
        if refreshed_summary is not None:
            refreshed_summaries.append(refreshed_summary)
    return refreshed_summaries


def sync_conduct_summary_after_record_save(record):
    record_model = type(record)
    if record.status in [record_model.Status.APPROVED, record_model.Status.REJECTED]:
        refresh_conduct_summary(record.student_id)


def sync_conduct_summary_after_record_delete(record):
    if record.student_id is None:
        return

    conduct_summary_model = _get_conduct_summary_model()
    summary = conduct_summary_model.objects.filter(student_id=record.student_id).first()
    if summary is not None:
        recalculate_conduct_summary(summary)


def sync_conduct_summaries_for_item(item):
    conduct_record_model = _get_conduct_record_model()
    student_ids = conduct_record_model.objects.filter(
        item=item,
        status=conduct_record_model.Status.APPROVED,
    ).values_list('student_id', flat=True).distinct()
    return refresh_conduct_summaries(student_ids)


def sync_conduct_summaries_for_category(category):
    conduct_record_model = _get_conduct_record_model()
    student_ids = conduct_record_model.objects.filter(
        item__category=category,
        status=conduct_record_model.Status.APPROVED,
    ).values_list('student_id', flat=True).distinct()
    return refresh_conduct_summaries(student_ids)


def sync_conduct_summaries_for_rule(rule):
    conduct_record_model = _get_conduct_record_model()
    student_ids = conduct_record_model.objects.filter(
        item__category__nature=rule.nature,
        severity_id=rule.severity_id,
        status=conduct_record_model.Status.APPROVED,
    ).values_list('student_id', flat=True).distinct()
    return refresh_conduct_summaries(student_ids)
