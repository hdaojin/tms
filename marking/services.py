from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from assessments.models import Assessment, AssessmentModule
from competitions.models import CompetitionModule, CompetitionResult, Competitor

from .models import (
    JudgementOption,
    MarkingAspect,
    MarkingParticipant,
    MarkingResult,
    MarkingResultImport,
    MarkingScheme,
    MarkingSchemeImport,
    MarkingSubCriterion,
    _target_standard_module,
)
from .parser import PARSER_VERSION, ParsedWorkbook, calculate_file_sha256, parse_marking_workbook


User = get_user_model()


def get_content_type_for_target(target):
    return ContentType.objects.get_for_model(target, for_concrete_model=False)


def get_allowed_target_models():
    return (CompetitionModule, AssessmentModule)


def validate_scheme_target(target, parsed: ParsedWorkbook):
    if not isinstance(target, get_allowed_target_models()):
        raise ValidationError("评分表只能绑定到竞赛官方模块或考核模块。")
    if isinstance(target, CompetitionModule):
        target_code = target.code
    else:
        target_code = target.module.code
    if parsed.module_code != target_code:
        raise ValidationError(f"评分表 ID 为 {parsed.module_code}，与绑定模块 {target_code} 不一致。")
    standard_module = _target_standard_module(target)
    if standard_module is None:
        raise ValidationError("绑定的竞赛官方模块尚未配置主标准模块映射。")
    return standard_module


@transaction.atomic
def create_scheme_from_upload(*, uploaded_file, target, user=None) -> MarkingScheme:
    parsed = parse_marking_workbook(uploaded_file)
    standard_module = validate_scheme_target(target, parsed)
    uploaded_file.seek(0)
    file_sha256 = calculate_file_sha256(uploaded_file)
    uploaded_file.seek(0)
    content_type = get_content_type_for_target(target)

    scheme_import = MarkingSchemeImport.objects.create(
        file=uploaded_file,
        original_filename=getattr(uploaded_file, "name", ""),
        file_sha256=file_sha256,
        parser_version=PARSER_VERSION,
        parse_summary=parsed.summary(),
        target_content_type=content_type,
        target_object_id=target.pk,
        uploaded_by=user if getattr(user, "is_authenticated", False) else None,
    )
    scheme = MarkingScheme.objects.create(
        source_import=scheme_import,
        standard_module=standard_module,
        target_content_type=content_type,
        target_object_id=target.pk,
        title=parsed.title or scheme_import.original_filename,
        module_code=parsed.module_code,
        module_name=parsed.module_name,
        total_mark=parsed.total_mark,
        parser_version=PARSER_VERSION,
    )

    subcriterion_map = {}
    for parsed_subcriterion in parsed.subcriteria:
        subcriterion = MarkingSubCriterion.objects.create(
            scheme=scheme,
            code=parsed_subcriterion.code,
            name=parsed_subcriterion.name,
            day_of_marking=parsed_subcriterion.day_of_marking,
            sort_order=parsed_subcriterion.sort_order,
        )
        subcriterion_map[subcriterion.code] = subcriterion

    for parsed_aspect in parsed.aspects:
        aspect = MarkingAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion_map[parsed_aspect.subcriterion_code],
            code=parsed_aspect.code,
            aspect_type=parsed_aspect.aspect_type,
            description=parsed_aspect.description,
            command=parsed_aspect.command,
            requirement=parsed_aspect.requirement,
            wsos_section=parsed_aspect.wsos_section,
            calculation_row=parsed_aspect.calculation_row,
            max_mark=parsed_aspect.max_mark,
            source_row_number=parsed_aspect.source_row_number,
            sort_order=parsed_aspect.sort_order,
        )
        JudgementOption.objects.bulk_create(
            [
                JudgementOption(
                    aspect=aspect,
                    score_value=option.score_value,
                    description=option.description,
                    source_row_number=option.source_row_number,
                    sort_order=option.sort_order,
                )
                for option in parsed_aspect.judgement_options
            ]
        )

    return scheme


def _decimal_from_payload(value, field_name):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValidationError(f"{field_name} 必须是数值。")


def _load_json_payload(uploaded_file):
    uploaded_file.seek(0)
    try:
        raw = uploaded_file.read().decode("utf-8")
    except AttributeError:
        raw = uploaded_file.read()
    uploaded_file.seek(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"JSON 结果包格式错误：{exc}")


def _resolve_participant_identity(item: dict[str, Any]):
    user = None
    competitor = None
    external_identifier = str(item.get("external_identifier") or "").strip()
    user_id = item.get("user_id")
    username = str(item.get("username") or "").strip()
    competitor_id = item.get("competitor_id")

    if user_id:
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            raise ValidationError(f"未找到用户 ID：{user_id}。")
    elif username:
        user = User.objects.filter(username=username).first()
        if user is None:
            raise ValidationError(f"未找到用户名：{username}。")

    if competitor_id:
        competitor = Competitor.objects.select_related("person", "member").filter(pk=competitor_id).first()
        if competitor is None:
            raise ValidationError(f"未找到竞赛选手 ID：{competitor_id}。")

    if sum(bool(value) for value in (user, competitor, external_identifier)) != 1:
        raise ValidationError("每个参评对象必须且只能提供 user_id/username、competitor_id 或 external_identifier。")
    return user, competitor, external_identifier


def _participant_defaults(item, user, competitor, external_identifier, sort_order):
    if competitor is not None:
        display_name = item.get("display_name") or competitor.name
        organization = item.get("organization") or competitor.organization
        member_name = item.get("member_name") or (competitor.member.name if competitor.member_id else "")
    elif user is not None:
        display_name = item.get("display_name") or user.display_name
        organization = item.get("organization") or ""
        member_name = item.get("member_name") or ""
    else:
        display_name = item.get("display_name") or external_identifier
        organization = item.get("organization") or ""
        member_name = item.get("member_name") or ""
    return {
        "display_name": display_name,
        "organization": organization,
        "member_name": member_name,
        "snapshot": item.get("snapshot") or {},
        "sort_order": sort_order,
    }


def _update_official_result(participant: MarkingParticipant, official_result: dict[str, Any] | None):
    if not official_result or participant.competitor_id is None:
        return None
    defaults = {}
    for field in ("score_100", "score_700"):
        value = _decimal_from_payload(official_result.get(field), field)
        if value is not None:
            defaults[field] = value
    if official_result.get("rank") not in (None, ""):
        defaults["rank"] = int(official_result["rank"])
    if official_result.get("medal"):
        defaults["medal"] = official_result["medal"]
    if not defaults:
        return None
    result, _ = CompetitionResult.objects.update_or_create(
        competitor=participant.competitor,
        defaults=defaults,
    )
    return result


@transaction.atomic
def import_result_package(*, scheme: MarkingScheme, uploaded_file, user=None) -> MarkingResultImport:
    payload = _load_json_payload(uploaded_file)
    participants = payload.get("participants")
    if not isinstance(participants, list) or not participants:
        raise ValidationError("JSON 结果包必须包含非空 participants 数组。")

    aspects = {aspect.code: aspect for aspect in scheme.aspects.all()}
    if not aspects:
        raise ValidationError("当前评分方案没有评分点，无法导入结果。")

    uploaded_file.seek(0)
    file_sha256 = calculate_file_sha256(uploaded_file)
    uploaded_file.seek(0)

    result_import = MarkingResultImport.objects.create(
        scheme=scheme,
        file=uploaded_file,
        original_filename=getattr(uploaded_file, "name", ""),
        file_sha256=file_sha256,
        imported_by=user if getattr(user, "is_authenticated", False) else None,
    )

    result_count = 0
    official_result_count = 0
    for index, participant_item in enumerate(participants):
        if not isinstance(participant_item, dict):
            raise ValidationError(f"participants[{index}] 必须是对象。")
        user_obj, competitor, external_identifier = _resolve_participant_identity(participant_item)
        lookup = {"scheme": scheme}
        if user_obj is not None:
            lookup["user"] = user_obj
        elif competitor is not None:
            lookup["competitor"] = competitor
        else:
            lookup["external_identifier"] = external_identifier
        participant, _ = MarkingParticipant.objects.update_or_create(
            **lookup,
            defaults=_participant_defaults(participant_item, user_obj, competitor, external_identifier, index),
        )
        if _update_official_result(participant, participant_item.get("official_result")) is not None:
            official_result_count += 1

        result_items = participant_item.get("results") or []
        if not isinstance(result_items, list):
            raise ValidationError(f"{participant.display_name} 的 results 必须是数组。")
        for result_item in result_items:
            aspect_code = str(result_item.get("aspect_code") or "").strip()
            aspect = aspects.get(aspect_code)
            if aspect is None:
                raise ValidationError(f"{participant.display_name} 引用了不存在的评分点编号：{aspect_code}。")
            score = _decimal_from_payload(result_item.get("score"), "score")
            if score is None:
                raise ValidationError(f"{participant.display_name} / {aspect_code} 缺少 score。")
            graded_at = result_item.get("graded_at")
            graded_at_value = parse_datetime(graded_at) if graded_at else None
            MarkingResult.objects.update_or_create(
                participant=participant,
                aspect=aspect,
                defaults={
                    "score_awarded": score,
                    "source": result_item.get("source") or MarkingResult.Source.CMP,
                    "evidence": result_item.get("evidence") or "",
                    "raw_payload": result_item,
                    "graded_at": graded_at_value or timezone.now(),
                },
            )
            result_count += 1

    result_import.summary = {
        "participant_count": len(participants),
        "result_count": result_count,
        "official_result_count": official_result_count,
    }
    result_import.save(update_fields=["summary"])
    return result_import


def get_schemes_for_target(target):
    content_type = get_content_type_for_target(target)
    return MarkingScheme.objects.filter(
        target_content_type=content_type,
        target_object_id=target.pk,
    ).select_related("standard_module", "source_import")


def get_assessment_marking_score_map(assessment: Assessment):
    module_ids = list(AssessmentModule.objects.filter(assessment=assessment).values_list("pk", flat=True))
    if not module_ids:
        return {}
    content_type = ContentType.objects.get_for_model(AssessmentModule)
    scheme_rows = MarkingScheme.objects.filter(
        target_content_type=content_type,
        target_object_id__in=module_ids,
    ).values_list("pk", "target_object_id")
    scheme_to_module = dict(scheme_rows)
    if not scheme_to_module:
        return {}

    score_rows = (
        MarkingResult.objects.filter(
            participant__scheme_id__in=scheme_to_module.keys(),
            participant__user__isnull=False,
        )
        .values("participant__user_id", "participant__scheme_id")
        .annotate(total=Sum("score_awarded"))
    )
    score_map = {}
    for row in score_rows:
        module_id = scheme_to_module[row["participant__scheme_id"]]
        score_map[(row["participant__user_id"], module_id)] = row["total"] or Decimal("0.00")
    return score_map
