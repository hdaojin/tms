from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    Assessment,
    AssessmentAward,
    AssessmentFinalResult,
    AssessmentFinalScore,
    AssessmentResultAward,
)
from .selectors import calculated_final_result_preview, manageable_assessments_for


LIFECYCLE_TRANSITIONS = {
    "publish": ({Assessment.Status.DRAFT}, Assessment.Status.PUBLISHED),
    "start": ({Assessment.Status.PUBLISHED}, Assessment.Status.ACTIVE),
    "complete": ({Assessment.Status.ACTIVE}, Assessment.Status.COMPLETED),
    "archive": ({Assessment.Status.COMPLETED}, Assessment.Status.ARCHIVED),
    "cancel": (
        {Assessment.Status.DRAFT, Assessment.Status.PUBLISHED, Assessment.Status.ACTIVE},
        Assessment.Status.CANCELLED,
    ),
}
LIFECYCLE_ACTION_LABELS = {
    "publish": "发布",
    "start": "启动",
    "complete": "完成",
    "archive": "归档",
    "cancel": "取消",
}


def _ensure_assessment_manager(user, assessment):
    if not manageable_assessments_for(user, Assessment.objects.filter(pk=assessment.pk)).exists():
        raise PermissionDenied("您无权管理该竞赛或考核。")


def _ensure_result_permission(user, assessment, permission):
    if user is None or not user.has_perm(permission):
        raise PermissionDenied("您无权管理该竞赛或考核的最终结果。")
    _ensure_assessment_manager(user, assessment)


def _ensure_results_mutable(assessment):
    if assessment.results_published_at is not None:
        raise ValidationError("最终成绩已发布，不能再修改结果、成绩或奖项。")
    if assessment.status == Assessment.Status.ARCHIVED:
        raise ValidationError("已归档的竞赛或考核不能再修改最终结果。")


@transaction.atomic
def transition_assessment(assessment, action, user):
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    _ensure_assessment_manager(user, assessment)
    if action not in LIFECYCLE_TRANSITIONS:
        raise ValidationError("不支持的状态动作。")
    allowed_statuses, target_status = LIFECYCLE_TRANSITIONS[action]
    if assessment.status not in allowed_statuses:
        raise ValidationError(
            f"当前状态为“{assessment.get_status_display()}”，不能执行“{LIFECYCLE_ACTION_LABELS[action]}”。"
        )
    if action == "archive" and assessment.results_published_at is None:
        if assessment.participants.filter(role__category="competitor").exists():
            raise ValidationError("有参赛选手时必须先发布最终成绩，再归档。")

    now = timezone.now()
    assessment.status = target_status
    update_fields = ["status", "updated_at"]
    if action == "start" and assessment.started_at is None:
        assessment.started_at = now
        update_fields.append("started_at")
    if action in {"complete", "cancel"} and assessment.completed_at is None:
        assessment.completed_at = now
        update_fields.append("completed_at")
    assessment.save(update_fields=update_fields)
    return assessment


@transaction.atomic
def generate_final_results(assessment, user):
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    _ensure_result_permission(user, assessment, "assessments.add_assessmentfinalresult")
    if not user.has_perm("assessments.change_assessmentfinalresult"):
        raise PermissionDenied("生成最终结果需要新增和修改最终结果权限。")
    _ensure_results_mutable(assessment)
    if assessment.status != Assessment.Status.COMPLETED:
        raise ValidationError("只有已完成的竞赛或考核可以生成最终结果。")

    generated_at = timezone.now()
    created_count = 0
    updated_count = 0
    skipped_official_count = 0
    for preview in calculated_final_result_preview(assessment):
        final_result, created = AssessmentFinalResult.objects.select_for_update().get_or_create(
            participant=preview["participant"]
        )
        if final_result.is_official:
            skipped_official_count += 1
            continue
        metadata = dict(final_result.metadata)
        metadata["calculated_preview"] = {
            "generated_at": generated_at.isoformat(),
            "scored_count": preview["scored_count"],
            "expected_count": preview["expected_count"],
            "is_complete": preview["is_complete"],
        }
        final_result.rank = preview["rank"]
        final_result.metadata = metadata
        final_result.save(update_fields=["rank", "metadata", "updated_at"])
        AssessmentFinalScore.objects.update_or_create(
            final_result=final_result,
            score_type=AssessmentFinalScore.ScoreType.RAW,
            label="原始总分",
            defaults={
                "value": preview["raw_score"],
                "max_value": preview["max_score"],
                "order": 0,
                "metadata": {"source": "calculated_scoring_results"},
            },
        )
        if preview["percentage"] is not None:
            AssessmentFinalScore.objects.update_or_create(
                final_result=final_result,
                score_type=AssessmentFinalScore.ScoreType.PERCENTAGE,
                label="百分制成绩",
                defaults={
                    "value": preview["percentage"],
                    "max_value": Decimal("100.0000"),
                    "order": 10,
                    "metadata": {"source": "calculated_scoring_results"},
                },
            )
        else:
            AssessmentFinalScore.objects.filter(
                final_result=final_result,
                score_type=AssessmentFinalScore.ScoreType.PERCENTAGE,
                label="百分制成绩",
                metadata__source="calculated_scoring_results",
            ).delete()
        if created:
            created_count += 1
        else:
            updated_count += 1
    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_official_count": skipped_official_count,
    }


@transaction.atomic
def update_final_result_details(final_result, user, *, rank, notes, awards, score_rows):
    final_result = AssessmentFinalResult.objects.select_for_update().select_related("participant").get(
        pk=final_result.pk
    )
    assessment = Assessment.objects.select_for_update().get(pk=final_result.participant.assessment_id)
    _ensure_result_permission(user, assessment, "assessments.change_assessmentfinalresult")
    _ensure_results_mutable(assessment)
    awards = list(awards)
    if any(award.assessment_id != assessment.pk for award in awards):
        raise ValidationError("只能分配当前竞赛或考核配置的奖项。")

    changed = final_result.rank != rank or final_result.notes != notes
    final_result.rank = rank
    final_result.notes = notes
    desired_award_ids = {award.pk for award in awards}
    current_award_ids = set(final_result.award_links.values_list("award_id", flat=True))
    if desired_award_ids != current_award_ids:
        changed = True
        final_result.award_links.exclude(award_id__in=desired_award_ids).delete()
        for award in awards:
            AssessmentResultAward.objects.get_or_create(final_result=final_result, award=award)

    for row in score_rows:
        score_id = row.get("score_id")
        score = None
        if score_id:
            score = AssessmentFinalScore.objects.select_for_update().filter(
                pk=score_id,
                final_result=final_result,
            ).first()
            if score is None:
                raise ValidationError("最终成绩行不属于当前最终结果。")
        if row.get("delete"):
            if score is not None:
                score.delete()
                changed = True
            continue
        values = {
            "score_type": row["score_type"],
            "label": row["label"],
            "value": row["value"],
            "max_value": row.get("max_value"),
            "order": row.get("order") or 0,
        }
        if score is None:
            score = AssessmentFinalScore(final_result=final_result, **values)
            changed = True
        else:
            changed |= any(getattr(score, field) != value for field, value in values.items())
            for field, value in values.items():
                setattr(score, field, value)
        score.full_clean()
        score.save()

    if changed and final_result.is_official:
        final_result.is_official = False
        final_result.confirmed_by = None
        final_result.confirmed_at = None
    final_result.full_clean()
    final_result.save()
    return final_result


@transaction.atomic
def confirm_final_result(final_result, user):
    final_result = AssessmentFinalResult.objects.select_for_update().select_related("participant").get(
        pk=final_result.pk
    )
    assessment = Assessment.objects.select_for_update().get(pk=final_result.participant.assessment_id)
    _ensure_result_permission(user, assessment, "assessments.change_assessmentfinalresult")
    _ensure_results_mutable(assessment)
    if assessment.status != Assessment.Status.COMPLETED:
        raise ValidationError("只有已完成的竞赛或考核可以确认最终结果。")
    if not final_result.scores.exists():
        raise ValidationError("最终结果至少需要一条成绩后才能确认。")
    final_result.is_official = True
    final_result.confirmed_by = user
    final_result.confirmed_at = timezone.now()
    final_result.save(update_fields=["is_official", "confirmed_by", "confirmed_at", "updated_at"])
    return final_result


@transaction.atomic
def publish_final_results(assessment, user):
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    _ensure_result_permission(user, assessment, "assessments.change_assessmentfinalresult")
    if assessment.results_published_at is not None:
        return assessment
    if assessment.status != Assessment.Status.COMPLETED:
        raise ValidationError("只有已完成的竞赛或考核可以发布最终成绩。")
    participant_ids = list(
        assessment.participants.filter(role__category="competitor").values_list("pk", flat=True)
    )
    if not participant_ids:
        raise ValidationError("没有参赛选手，无法发布最终成绩。")
    official_results = AssessmentFinalResult.objects.filter(
        participant_id__in=participant_ids,
        is_official=True,
    )
    if official_results.count() != len(participant_ids):
        raise ValidationError("每名选手的最终结果都必须先完成确认。")
    if official_results.filter(scores__isnull=True).exists():
        raise ValidationError("每名选手的最终结果都必须至少包含一条成绩。")
    assessment.results_published_at = timezone.now()
    assessment.save(update_fields=["results_published_at", "updated_at"])
    return assessment


@transaction.atomic
def create_assessment_award(assessment, user, **values):
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    _ensure_result_permission(user, assessment, "assessments.add_assessmentaward")
    _ensure_results_mutable(assessment)
    award = AssessmentAward(assessment=assessment, **values)
    award.full_clean()
    award.save()
    return award
