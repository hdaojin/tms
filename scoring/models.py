from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .registry import PARSER_DEFINITIONS


class ScoringScheme(models.Model):
    event_module = models.ForeignKey(
        "events.EventModule",
        verbose_name="事件模块",
        on_delete=models.PROTECT,
        related_name="scoring_schemes",
    )
    source_asset = models.ForeignKey(
        "archives.ArchiveAsset",
        verbose_name="来源评分表",
        on_delete=models.PROTECT,
        related_name="scoring_schemes",
        null=True,
        blank=True,
    )
    title = models.CharField("标题", max_length=255)
    module_code = models.CharField("模块代码", max_length=50)
    module_name = models.CharField("模块名称", max_length=150)
    total_mark = models.DecimalField(
        "总分",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    parser_version = models.CharField("解析器版本", max_length=30, blank=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="导入人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imported_scoring_schemes",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "评分方案"
        verbose_name_plural = "评分方案"
        ordering = ["-created_at", "module_code", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["event_module", "module_code"],
                name="uniq_scoringscheme_eventmodule_code",
            ),
        ]

    @property
    def skill_project(self):
        return self.event_module.event.skill_project

    def clean(self):
        super().clean()
        if self.event_module_id and self.module_code and self.event_module.code != self.module_code:
            raise ValidationError({"module_code": f"评分表模块代码必须与事件模块一致：{self.event_module.code}。"})

    def __str__(self):
        return f"{self.module_code} - {self.module_name}"


class ScoringParserConfig(models.Model):
    parser_key = models.CharField("解析器标识", max_length=80, unique=True)
    display_name = models.CharField("显示名称", max_length=120)
    alias = models.CharField("别名", max_length=80, blank=True)
    description = models.TextField("说明", blank=True)
    is_enabled = models.BooleanField("启用", default=True)
    is_default = models.BooleanField("默认解析器", default=False)
    order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "评分表解析器"
        verbose_name_plural = "评分表解析器"
        ordering = ["order", "display_name", "parser_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=Q(is_default=True),
                name="uniq_default_scoring_parser_config",
            ),
        ]

    def clean(self):
        super().clean()
        if self.parser_key and self.parser_key not in PARSER_DEFINITIONS:
            raise ValidationError({"parser_key": "解析器标识必须来自系统内置解析器注册表。"})
        if self.is_default and not self.is_enabled:
            raise ValidationError({"is_default": "默认解析器必须处于启用状态。"})

    def save(self, *args, **kwargs):
        if self.is_default and not self.is_enabled:
            raise ValidationError({"is_default": "默认解析器必须处于启用状态。"})
        super().save(*args, **kwargs)

    def __str__(self):
        alias = f" ({self.alias})" if self.alias else ""
        return f"{self.display_name}{alias}"


class ScoringSchemeImport(models.Model):
    class Status(models.TextChoices):
        PARSED = "parsed", "已解析"
        CONFIRMED = "confirmed", "已确认"

    event_module = models.ForeignKey(
        "events.EventModule",
        verbose_name="事件模块",
        on_delete=models.PROTECT,
        related_name="scoring_scheme_imports",
    )
    source_asset = models.ForeignKey(
        "archives.ArchiveAsset",
        verbose_name="来源评分表",
        on_delete=models.PROTECT,
        related_name="scoring_scheme_imports",
    )
    scheme = models.ForeignKey(
        ScoringScheme,
        verbose_name="生成评分方案",
        on_delete=models.SET_NULL,
        related_name="scheme_imports",
        null=True,
        blank=True,
    )
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.PARSED)
    parser_key = models.CharField("解析器标识", max_length=80)
    parser_display_name = models.CharField("解析器显示名称", max_length=120)
    parser_alias = models.CharField("解析器别名", max_length=80, blank=True)
    parser_description = models.TextField("解析器说明", blank=True)
    title = models.CharField("标题", max_length=255)
    module_code = models.CharField("模块代码", max_length=50)
    module_name = models.CharField("模块名称", max_length=150)
    module_mark = models.DecimalField("模块总分", max_digits=8, decimal_places=2)
    total_mark = models.DecimalField("评分点总分", max_digits=8, decimal_places=2)
    raw_snapshot = models.JSONField("原始快照", default=dict, blank=True)
    field_mapping = models.JSONField("字段映射", default=dict, blank=True)
    validation_report = models.JSONField("校验报告", default=dict, blank=True)
    parsed_payload = models.JSONField("解析数据", default=dict, blank=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="导入人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scoring_scheme_imports",
    )
    imported_at = models.DateTimeField("导入时间", auto_now_add=True)
    confirmed_at = models.DateTimeField("确认时间", null=True, blank=True)

    class Meta:
        verbose_name = "评分表导入记录"
        verbose_name_plural = "评分表导入记录"
        ordering = ["-imported_at", "-pk"]

    def confirm(self, scheme):
        self.scheme = scheme
        self.status = self.Status.CONFIRMED
        self.confirmed_at = timezone.now()
        self.save(update_fields=["scheme", "status", "confirmed_at"])

    def __str__(self):
        return f"{self.module_code} - {self.module_name} / {self.get_status_display()}"


class ScoringSubCriterion(models.Model):
    scheme = models.ForeignKey(
        ScoringScheme,
        verbose_name="评分方案",
        on_delete=models.CASCADE,
        related_name="subcriteria",
    )
    code = models.CharField("子评分项编号", max_length=30)
    name = models.CharField("子评分项名称或描述", max_length=300)
    day_of_marking = models.CharField("评分日", max_length=50, blank=True)
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = "评分子项"
        verbose_name_plural = "评分子项"
        ordering = ["scheme", "order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["scheme", "code"], name="uniq_scoring_subcriterion"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ScoringAspect(models.Model):
    class AspectType(models.TextChoices):
        MEASUREMENT = "M", "测量"
        JUDGEMENT = "J", "评价"

    scheme = models.ForeignKey(ScoringScheme, verbose_name="评分方案", on_delete=models.CASCADE, related_name="aspects")
    subcriterion = models.ForeignKey(
        ScoringSubCriterion,
        verbose_name="评分子项",
        on_delete=models.PROTECT,
        related_name="aspects",
    )
    code = models.CharField("评分点编号", max_length=50)
    aspect_type = models.CharField("评分类型", max_length=1, choices=AspectType.choices)
    description = models.TextField("评分点")
    command = models.TextField("命令或操作", blank=True)
    requirement = models.TextField("期望结果", blank=True)
    calculation_row = models.CharField("Calculation Row", max_length=100, blank=True)
    max_mark = models.DecimalField(
        "分值",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    source_row_number = models.PositiveIntegerField("来源行号")
    order = models.PositiveIntegerField("排序", default=0)
    knowledge_evidences = GenericRelation(
        "knowledge.KnowledgeEvidence",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
        related_query_name="scoring_aspect",
    )

    class Meta:
        verbose_name = "评分点"
        verbose_name_plural = "评分点"
        ordering = ["scheme", "subcriterion__order", "order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["scheme", "code"], name="uniq_scoring_aspect_code"),
            models.UniqueConstraint(fields=["scheme", "source_row_number"], name="uniq_scoring_aspect_source_row"),
        ]

    def clean(self):
        super().clean()
        if self.scheme_id and self.subcriterion_id and self.subcriterion.scheme_id != self.scheme_id:
            raise ValidationError({"subcriterion": "评分子项必须属于当前评分方案。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.description}"


class JudgementOption(models.Model):
    aspect = models.ForeignKey(
        ScoringAspect,
        verbose_name="评价评分点",
        on_delete=models.CASCADE,
        related_name="judgement_options",
    )
    score_value = models.DecimalField("分档值", max_digits=6, decimal_places=2)
    description = models.TextField("分档说明")
    source_row_number = models.PositiveIntegerField("来源行号")
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = "评价分档"
        verbose_name_plural = "评价分档"
        ordering = ["aspect", "order", "score_value"]
        constraints = [
            models.UniqueConstraint(fields=["aspect", "score_value"], name="uniq_judgement_option"),
        ]

    def __str__(self):
        return f"{self.score_value} - {self.description}"


class ScoringParticipant(models.Model):
    scheme = models.ForeignKey(ScoringScheme, verbose_name="评分方案", on_delete=models.CASCADE, related_name="participants")
    event_participant = models.ForeignKey(
        "events.EventParticipant",
        verbose_name="事件参与人员",
        on_delete=models.PROTECT,
        related_name="scoring_participations",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="关联用户",
        on_delete=models.PROTECT,
        related_name="scoring_participations",
        null=True,
        blank=True,
    )
    external_identifier = models.CharField("外部编号", max_length=100, blank=True)
    display_name = models.CharField("显示名称", max_length=200)
    organization = models.CharField("所属单位", max_length=200, blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "参评对象"
        verbose_name_plural = "参评对象"
        ordering = ["scheme", "order", "display_name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "event_participant"],
                condition=Q(event_participant__isnull=False),
                name="uniq_scoringparticipant_event_participant",
            ),
            models.UniqueConstraint(
                fields=["scheme", "user"],
                condition=Q(user__isnull=False),
                name="uniq_scoringparticipant_user",
            ),
            models.UniqueConstraint(
                fields=["scheme", "external_identifier"],
                condition=~Q(external_identifier=""),
                name="uniq_scoringparticipant_external",
            ),
        ]

    def clean(self):
        super().clean()
        identities = [bool(self.event_participant_id), bool(self.user_id), bool(self.external_identifier)]
        if sum(identities) != 1:
            raise ValidationError("参评对象必须且只能绑定事件参与人员、用户或外部编号中的一种。")
        if self.event_participant_id and self.scheme_id:
            if self.event_participant.event_id != self.scheme.event_module.event_id:
                raise ValidationError({"event_participant": "事件参与人员必须属于评分方案对应事件。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class ScoringResult(models.Model):
    class Source(models.TextChoices):
        CMP = "cmp", "CMP 导入"
        IMPORTED = "imported", "文件导入"
        MANUAL = "manual", "人工录入"

    participant = models.ForeignKey(
        ScoringParticipant,
        verbose_name="参评对象",
        on_delete=models.CASCADE,
        related_name="results",
    )
    aspect = models.ForeignKey(ScoringAspect, verbose_name="评分点", on_delete=models.PROTECT, related_name="results")
    score_awarded = models.DecimalField(
        "得分",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    source = models.CharField("来源", max_length=20, choices=Source.choices, default=Source.IMPORTED)
    evidence = models.TextField("证据摘要", blank=True)
    raw_payload = models.JSONField("原始结果", default=dict, blank=True)
    graded_at = models.DateTimeField("评分时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "评分结果"
        verbose_name_plural = "评分结果"
        ordering = ["participant", "aspect__order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "aspect"], name="uniq_scoring_result"),
        ]

    def clean(self):
        super().clean()
        if self.participant_id and self.aspect_id and self.participant.scheme_id != self.aspect.scheme_id:
            raise ValidationError("评分点不属于当前参评对象的评分方案。")
        if self.aspect_id and self.score_awarded > self.aspect.max_mark:
            raise ValidationError({"score_awarded": f"得分不能超过评分点分值 {self.aspect.max_mark}。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.participant} / {self.aspect}: {self.score_awarded}"


class ScoringResultImport(models.Model):
    scheme = models.ForeignKey(ScoringScheme, verbose_name="评分方案", on_delete=models.PROTECT, related_name="result_imports")
    source_asset = models.ForeignKey(
        "archives.ArchiveAsset",
        verbose_name="来源结果包",
        on_delete=models.PROTECT,
        related_name="scoring_result_imports",
    )
    summary = models.JSONField("导入摘要", default=dict, blank=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="导入者",
        on_delete=models.SET_NULL,
        related_name="scoring_result_imports",
        null=True,
        blank=True,
    )
    imported_at = models.DateTimeField("导入时间", auto_now_add=True)

    class Meta:
        verbose_name = "结果包导入"
        verbose_name_plural = "结果包导入"
        ordering = ["-imported_at", "-pk"]

    def __str__(self):
        return f"{self.scheme} / {self.source_asset.filename}"

# Create your models here.

