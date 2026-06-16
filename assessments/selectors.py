from __future__ import annotations

from decimal import Decimal

from django.db.models import Prefetch
from django.utils import timezone

from marking.services import get_assessment_marking_score_map, get_schemes_for_target

from .models import Assessment, AssessmentModule
from .permissions import (
    can_lock_assessment_module,
    can_manage_assessment_module,
    can_unlock_assessment_module,
    is_coach,
)


def _get_assessment_modules_queryset(assessment):
    return (
        AssessmentModule.objects.select_related("module", "responsible_coach")
        .prefetch_related("attachments")
        .filter(assessment=assessment)
        .order_by("sort_order", "module__code", "pk")
    )


def assessment_module_counts_towards_ranking(assessment_module):
    return assessment_module.counts_towards_ranking


def _get_all_assessments_queryset():
    return (
        Assessment.objects.select_related("training_cycle")
        .prefetch_related("assessmentmodule_set__module")
        .order_by("-start_date")
    )


def _get_managed_assessments_queryset(user):
    return (
        Assessment.objects.filter(assessmentmodule__responsible_coach=user)
        .select_related("training_cycle")
        .prefetch_related("assessmentmodule_set__module")
        .distinct()
        .order_by("-start_date")
    )


def _get_participant_assessments_queryset(user):
    modules_prefetch = Prefetch(
        "assessmentmodule_set",
        queryset=AssessmentModule.objects.select_related("module").order_by("sort_order", "module__code", "pk"),
        to_attr="user_modules_info",
    )
    return (
        Assessment.objects.filter(participants=user)
        .select_related("training_cycle")
        .prefetch_related(modules_prefetch)
        .order_by("-start_date")
    )


def _split_assessments_by_date(assessments, today):
    current_assessments = []
    past_assessments = []
    upcoming_assessments = []

    for assessment in assessments:
        if assessment.end_date < today:
            past_assessments.append(assessment)
        elif assessment.start_date > today:
            upcoming_assessments.append(assessment)
        else:
            current_assessments.append(assessment)

    return current_assessments, past_assessments, upcoming_assessments


def build_assessment_list_context(user, today=None):
    today = today or timezone.now().date()
    can_view_all = user.is_superuser or user.has_perm("assessments.view_all_scores")
    managed_assessments = Assessment.objects.none()
    if is_coach(user):
        managed_assessments = _get_managed_assessments_queryset(user)

    show_management_actions = can_view_all or managed_assessments.exists()
    if can_view_all:
        assessments = _get_all_assessments_queryset()
    elif show_management_actions:
        assessments = managed_assessments
    else:
        assessments = _get_participant_assessments_queryset(user)

    current_assessments, past_assessments, upcoming_assessments = _split_assessments_by_date(
        assessments,
        today,
    )
    if not show_management_actions:
        populate_user_assessment_history(past_assessments, user)

    return {
        "can_view_all": can_view_all,
        "show_management_actions": show_management_actions,
        "current_assessments": current_assessments,
        "past_assessments": past_assessments,
        "upcoming_assessments": upcoming_assessments,
    }


def populate_user_assessment_history(past_assessments, user):
    for assessment in past_assessments:
        score_map = get_assessment_marking_score_map(assessment)
        my_total = Decimal("0.00")
        my_grand_total = Decimal("0.00")
        assessment.max_ranking_score = Decimal("0.00")
        assessment.max_grand_total_score = Decimal("0.00")
        ranking_module_ids = []

        if hasattr(assessment, "user_modules_info"):
            for assessment_module in assessment.user_modules_info:
                score_val = score_map.get((user.pk, assessment_module.pk))
                assessment_module.user_marking_score = score_val

                my_grand_total += score_val or Decimal("0.00")
                assessment.max_grand_total_score += assessment_module.max_score

                if assessment_module_counts_towards_ranking(assessment_module):
                    ranking_module_ids.append(assessment_module.pk)
                    my_total += score_val or Decimal("0.00")
                    assessment.max_ranking_score += assessment_module.max_score

        assessment.my_total_score = my_total
        assessment.my_grand_total_score = my_grand_total

        my_rank = "-"
        if ranking_module_ids:
            totals = []
            for participant in assessment.participants.all():
                total = sum(
                    (score_map.get((participant.pk, module_id)) or Decimal("0.00"))
                    for module_id in ranking_module_ids
                )
                totals.append((participant.pk, total))
            totals.sort(key=lambda item: item[1], reverse=True)
            current_rank = 1
            for index, (participant_id, total) in enumerate(totals):
                if index > 0 and total < totals[index - 1][1]:
                    current_rank = index + 1
                if participant_id == user.pk:
                    my_rank = current_rank
                    break

        assessment.my_rank = my_rank

    return past_assessments


def build_assessment_score_table_context(assessment, sort_param, user=None):
    sort_param = (sort_param or "-total").strip() or "-total"
    modules = list(_get_assessment_modules_queryset(assessment))

    for assessment_module in modules:
        assessment_module.marking_schemes = list(get_schemes_for_target(assessment_module))
        assessment_module.has_marking_scheme = bool(assessment_module.marking_schemes)
        attachments = list(assessment_module.attachments.all())
        assessment_module.attachment_count = len(attachments)
        assessment_module.has_attachments = bool(attachments)
        assessment_module.has_any_material = bool(
            assessment_module.question_file
            or assessment_module.scoring_standard_file
            or assessment_module.scoring_sheet_file
            or assessment_module.scoring_script_file
            or assessment_module.has_attachments
        )
        can_manage = can_manage_assessment_module(user, assessment_module) if user else False
        can_lock = can_lock_assessment_module(user, assessment_module) if user else False
        can_unlock = can_unlock_assessment_module(user) if user else False
        assessment_module.can_manage = can_manage
        assessment_module.can_manage_scores = can_manage
        assessment_module.can_manage_materials = can_manage
        assessment_module.can_lock_scores = can_lock and not assessment_module.is_locked
        assessment_module.can_unlock_scores = can_unlock and assessment_module.is_locked
        assessment_module.can_lock_materials = (
            can_lock and not assessment_module.is_material_locked
        )
        assessment_module.can_unlock_materials = (
            can_unlock and assessment_module.is_material_locked
        )

    participants = assessment.participants.all().order_by(
        "last_name", "first_name", "username"
    )
    score_map = get_assessment_marking_score_map(assessment)

    table_rows = []
    for participant in participants:
        row = {
            "user": participant,
            "scores": [],
        }
        total_score = Decimal("0.00")
        rank_score = Decimal("0.00")

        for assessment_module in modules:
            has_score = (participant.pk, assessment_module.pk) in score_map
            value = score_map.get((participant.pk, assessment_module.pk), Decimal("0.00"))
            row["scores"].append(
                {
                    "module_id": assessment_module.pk,
                    "val": value,
                    "has_score": has_score,
                    "can_manage": assessment_module.can_manage,
                }
            )
            if has_score:
                total_score += value
                if assessment_module_counts_towards_ranking(assessment_module):
                    rank_score += value

        row["total"] = total_score
        row["rank_score"] = rank_score
        table_rows.append(row)

    if sort_param.startswith("-"):
        sort_key = sort_param[1:]
        reverse = True
    else:
        sort_key = sort_param
        reverse = False

    def get_sort_value(row):
        if sort_key == "total":
            return row["rank_score"]
        if sort_key == "grand_total":
            return row["total"]
        if sort_key.startswith("module_"):
            try:
                module_id = int(sort_key.split("_")[1])
            except (ValueError, IndexError):
                return 0
            for score in row["scores"]:
                if score["module_id"] == module_id:
                    return score["val"]
        return 0

    table_rows.sort(key=lambda item: item["rank_score"], reverse=True)
    current_rank = 1
    for index, row in enumerate(table_rows):
        if index > 0 and row["rank_score"] < table_rows[index - 1]["rank_score"]:
            current_rank = index + 1
        row["rank"] = current_rank

    if sort_param != "-total":
        table_rows.sort(key=get_sort_value, reverse=reverse)

    max_ranking_score = 0
    max_grand_total_score = 0
    for assessment_module in modules:
        max_grand_total_score += assessment_module.max_score
        if assessment_module_counts_towards_ranking(assessment_module):
            max_ranking_score += assessment_module.max_score

    return {
        "assessment": assessment,
        "modules": modules,
        "table_rows": table_rows,
        "current_sort": sort_param,
        "max_ranking_score": max_ranking_score,
        "max_grand_total_score": max_grand_total_score,
    }
