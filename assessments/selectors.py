from __future__ import annotations

from .models import AssessmentModule, Score
from .permissions import (
    can_lock_assessment_module,
    can_manage_assessment_module,
    can_unlock_assessment_module,
)


def _get_assessment_modules_queryset(assessment):
    return (
        AssessmentModule.objects.select_related("module", "responsible_coach")
        .prefetch_related("attachments")
        .filter(assessment=assessment)
        .order_by("sort_order", "module__code", "pk")
    )


def build_assessment_score_table_context(assessment, sort_param, user=None):
    sort_param = (sort_param or "-total").strip() or "-total"
    modules = list(_get_assessment_modules_queryset(assessment))

    for assessment_module in modules:
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
    all_scores = Score.objects.filter(assessment_module__assessment=assessment).select_related(
        "user", "assessment_module"
    )
    score_map = {
        (score.user_id, score.assessment_module_id): score for score in all_scores
    }

    table_rows = []
    for participant in participants:
        row = {
            "user": participant,
            "scores": [],
        }
        total_score = 0
        rank_score = 0

        for assessment_module in modules:
            score_obj = score_map.get((participant.pk, assessment_module.pk))
            value = score_obj.score if score_obj else 0
            row["scores"].append(
                {
                    "module_id": assessment_module.pk,
                    "val": value,
                    "obj": score_obj,
                    "can_manage": assessment_module.can_manage,
                }
            )
            if score_obj:
                total_score += value
                if "english" not in assessment_module.module.name.lower():
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
        if "english" not in assessment_module.module.name.lower():
            max_ranking_score += assessment_module.max_score

    return {
        "assessment": assessment,
        "modules": modules,
        "table_rows": table_rows,
        "current_sort": sort_param,
        "max_ranking_score": max_ranking_score,
        "max_grand_total_score": max_grand_total_score,
    }