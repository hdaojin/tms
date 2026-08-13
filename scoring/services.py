from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from archives.models import ArchiveAsset
from events.models import EventModule
from knowledge.services import create_evidence_from_scoring_aspect

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
    for index, definition in enumerate(PARSER_DEFINITIONS.values()):
        config, created = ScoringParserConfig.objects.get_or_create(
            parser_key=definition.key,
            defaults={
                "display_name": definition.display_name,
                "alias": definition.alias,
                "description": definition.description,
                "is_enabled": True,
                "is_default": False,
                "order": index,
            },
        )
        if created:
            created_configs.append(config)
    if not ScoringParserConfig.objects.filter(is_default=True, is_enabled=True).exists():
        fallback = ScoringParserConfig.objects.filter(parser_key=default_parser_key()).first()
        if fallback:
            if not fallback.is_enabled:
                fallback.is_enabled = True
                fallback.save(update_fields=["is_enabled", "updated_at"])
            set_default_parser_config(fallback)
    return created_configs


@transaction.atomic
def set_default_parser_config(config: ScoringParserConfig) -> ScoringParserConfig:
    """Atomically make one enabled parser configuration the default."""
    if not config.pk:
        raise ValidationError("只能设置已经保存的评分解析器为默认解析器。")

    locked_configs = list(ScoringParserConfig.objects.select_for_update().order_by("pk"))
    target = next((locked_config for locked_config in locked_configs if locked_config.pk == config.pk), None)
    if target is None:
        raise ScoringParserConfig.DoesNotExist(f"不存在主键为 {config.pk} 的评分解析器配置。")
    target.full_clean()
    if not target.is_enabled:
        raise ValidationError({"is_default": "默认解析器必须处于启用状态。"})

    ScoringParserConfig.objects.filter(is_default=True).exclude(pk=target.pk).update(is_default=False)
    target.is_default = True
    target.save(update_fields=["is_default", "updated_at"])
    return target


def enabled_parser_configs():
    sync_parser_configs()
    return ScoringParserConfig.objects.filter(is_enabled=True).order_by("order", "display_name", "parser_key")


def default_parser_config():
    sync_parser_configs()
    config = ScoringParserConfig.objects.filter(is_enabled=True, is_default=True).first()
    if config:
        return config
    return ScoringParserConfig.objects.filter(is_enabled=True).order_by("order", "display_name", "parser_key").first()


@transaction.atomic
def parse_scheme_upload(event_module, uploaded_file, parser_config, user=None):
    definition = get_parser_definition(parser_config.parser_key)
    parsed = definition.parse(uploaded_file, expected_module_code=event_module.code)
    try:
        uploaded_file.seek(0)
    except (AttributeError, OSError):
        pass
    asset = ArchiveAsset.objects.create(
        target_content_type=ContentType.objects.get_for_model(event_module),
        target_object_id=event_module.pk,
        skill_project=event_module.event.skill_project,
        asset_type=ArchiveAsset.AssetType.MARKING_SCHEME,
        title=f"{event_module} 评分表",
        file=uploaded_file,
        original_filename=getattr(uploaded_file, "name", ""),
        business_date=event_module.event.start_date,
        uploaded_by=user,
        metadata={
            "parser_key": parser_config.parser_key,
            "parser_display_name": parser_config.display_name,
            "parser_alias": parser_config.alias,
        },
    )
    return ScoringSchemeImport.objects.create(
        event_module=event_module,
        source_asset=asset,
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
    if not scheme_import.pk:
        raise ValidationError("只能确认已经保存的评分方案导入记录。")

    requested_import = scheme_import
    scheme_import = ScoringSchemeImport.objects.select_for_update().get(pk=scheme_import.pk)
    if scheme_import.status == ScoringSchemeImport.Status.CONFIRMED and scheme_import.scheme_id:
        confirmed_scheme = scheme_import.scheme
        requested_import.scheme = confirmed_scheme
        requested_import.status = scheme_import.status
        requested_import.confirmed_at = scheme_import.confirmed_at
        return confirmed_scheme

    event_module = EventModule.objects.select_for_update().get(pk=scheme_import.event_module_id)
    scheme = (
        ScoringScheme.objects.select_for_update()
        .filter(
            event_module_id=event_module.pk,
            module_code=scheme_import.module_code,
        )
        .first()
    )
    if scheme and ScoringResult.objects.filter(aspect__scheme=scheme).exists():
        raise ValidationError("当前事件模块已存在评分结果，不能覆盖评分方案。")

    if scheme is None:
        scheme = ScoringScheme(
            event_module=event_module,
            module_code=scheme_import.module_code,
        )
        created = True
    else:
        created = False
    scheme.source_asset = scheme_import.source_asset
    scheme.title = scheme_import.title
    scheme.module_name = scheme_import.module_name
    scheme.total_mark = scheme_import.total_mark
    scheme.parser_version = scheme_import.parser_key
    scheme.imported_by = user or scheme_import.imported_by
    scheme.full_clean()
    scheme.save()
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
    requested_import.scheme = scheme
    requested_import.status = scheme_import.status
    requested_import.confirmed_at = scheme_import.confirmed_at
    return scheme


@transaction.atomic
def create_scheme_from_upload(event_module, uploaded_file, user=None, parser_config=None):
    parser_config = parser_config or default_parser_config()
    scheme_import = parse_scheme_upload(event_module, uploaded_file, parser_config, user=user)
    return confirm_scheme_import(scheme_import, user=user)

