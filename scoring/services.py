from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from assessments.models import AssessmentDocument
from evidence.services import create_evidence_from_scoring_aspect

from .models import (
    JudgementOption,
    ScoringAspect,
    ScoringParserConfig,
    ScoringResult,
    ScoringScheme,
    ScoringSchemeImport,
    ScoringSubCriterion,
)
from .registry import PARSER_DEFINITIONS, default_parser_key, get_parser_definition


def sync_parser_configs():
    created_configs = []
    existing_default = ScoringParserConfig.objects.filter(is_default=True).first()
    for index, definition in enumerate(PARSER_DEFINITIONS.values()):
        config, created = ScoringParserConfig.objects.get_or_create(
            parser_key=definition.key,
            defaults={
                "display_name": definition.display_name,
                "alias": definition.alias,
                "description": definition.description,
                "is_enabled": True,
                "is_default": definition.key == default_parser_key() and existing_default is None,
                "order": index,
            },
        )
        if created:
            created_configs.append(config)
    if not ScoringParserConfig.objects.filter(is_default=True, is_enabled=True).exists():
        fallback = ScoringParserConfig.objects.filter(parser_key=default_parser_key()).first()
        if fallback:
            fallback.is_enabled = True
            fallback.is_default = True
            fallback.save(update_fields=["is_enabled", "is_default", "updated_at"])
    return created_configs


def enabled_parser_configs():
    sync_parser_configs()
    return ScoringParserConfig.objects.filter(is_enabled=True).order_by("order", "display_name", "parser_key")


def default_parser_config():
    sync_parser_configs()
    return (
        ScoringParserConfig.objects.filter(is_enabled=True, is_default=True).first()
        or ScoringParserConfig.objects.filter(is_enabled=True).order_by("order", "display_name").first()
    )


@transaction.atomic
def parse_scheme_document(document, parser_config, user=None):
    if document.document_type != AssessmentDocument.DocumentType.MARKING_SCHEME or not document.module_id:
        raise ValidationError("只能解析绑定评测模块的评分表资料。")
    definition = get_parser_definition(parser_config.parser_key)
    with document.file.open("rb") as source:
        parsed = definition.parse(source, expected_module_code=document.module.code)
    return ScoringSchemeImport.objects.create(
        assessment_module=document.module,
        source_document=document,
        parser_key=parser_config.parser_key,
        parser_display_name=parser_config.display_name,
        parser_alias=parser_config.alias,
        parser_description=parser_config.description,
        title=parsed.title,
        module_code=parsed.module_code,
        module_name=parsed.module_name,
        module_mark=parsed.module_mark,
        total_mark=parsed.total_mark,
        raw_snapshot=parsed.raw_snapshot,
        field_mapping=parsed.field_mapping,
        validation_report=parsed.validation_report,
        parsed_payload=parsed.as_payload(),
        imported_by=user,
    )


@transaction.atomic
def confirm_scheme_import(scheme_import: ScoringSchemeImport, user=None):
    scheme_import = ScoringSchemeImport.objects.select_for_update().get(pk=scheme_import.pk)
    if scheme_import.status == ScoringSchemeImport.Status.CONFIRMED and scheme_import.scheme_id:
        return scheme_import.scheme
    existing_scheme = ScoringScheme.objects.filter(
        assessment_module=scheme_import.assessment_module,
        module_code=scheme_import.module_code,
    ).first()
    if existing_scheme and ScoringResult.objects.filter(aspect__scheme=existing_scheme).exists():
        raise ValidationError("当前评测模块已存在评分结果，不能覆盖评分方案。")
    scheme, created = ScoringScheme.objects.update_or_create(
        assessment_module=scheme_import.assessment_module,
        module_code=scheme_import.module_code,
        defaults={
            "source_document": scheme_import.source_document,
            "title": scheme_import.title,
            "module_name": scheme_import.module_name,
            "total_mark": scheme_import.total_mark,
            "parser_version": scheme_import.parser_key,
            "imported_by": user or scheme_import.imported_by,
        },
    )
    if not created:
        scheme.aspects.all().delete()
        scheme.subcriteria.all().delete()
    for subcriterion_payload in scheme_import.parsed_payload.get("subcriteria", []):
        subcriterion = ScoringSubCriterion.objects.create(
            scheme=scheme,
            code=subcriterion_payload["code"],
            name=subcriterion_payload["name"],
            day_of_marking=subcriterion_payload.get("day_of_marking", ""),
            order=subcriterion_payload.get("order", 0),
        )
        for aspect_payload in subcriterion_payload.get("aspects", []):
            aspect = ScoringAspect.objects.create(
                scheme=scheme,
                subcriterion=subcriterion,
                code=aspect_payload["code"],
                aspect_type=aspect_payload["aspect_type"],
                description=aspect_payload["description"],
                command=aspect_payload.get("command", ""),
                requirement=aspect_payload.get("requirement", ""),
                calculation_row=aspect_payload.get("calculation_row", ""),
                max_mark=aspect_payload["max_mark"],
                source_row_number=aspect_payload["source_row_number"],
                order=aspect_payload.get("order", 0),
            )
            for option_payload in aspect_payload.get("judgement_options", []):
                JudgementOption.objects.create(
                    aspect=aspect,
                    score_value=option_payload["score_value"],
                    description=option_payload["description"],
                    source_row_number=option_payload["source_row_number"],
                    order=option_payload.get("order", 0),
                )
            create_evidence_from_scoring_aspect(aspect, created_by=user or scheme_import.imported_by)
    scheme_import.confirm(scheme)
    return scheme


@transaction.atomic
def create_scheme_from_document(document, user=None, parser_config=None):
    scheme_import = parse_scheme_document(document, parser_config or default_parser_config(), user=user)
    return confirm_scheme_import(scheme_import, user=user)
