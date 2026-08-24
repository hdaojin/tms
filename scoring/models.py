from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .registry import PARSER_DEFINITIONS


class ScoringScheme(models.Model):
    assessment_module = models.ForeignKey(
        "assessments.AssessmentModule",
        verbose_name="评测模块",
        on_delete=models.PROTECT,
        related_name="scoring_schemes",
    )
    source_document = models.ForeignKey(
        "assessments.AssessmentDocument",
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
                fields=["assessment_module", "module_code"],
                name="uniq_scoringscheme_assessmentmodule_code",
            ),
        ]

    @property
    def skill_project(self):
        return self.assessment_module.assessment.skill_project

    def clean(self):
        super().clean()
        if self.assessment_module_id and self.module_code and self.assessment_module.code != self.module_code:
            raise ValidationError({"module_code": f"评分表模块代码必须与评测模块一致：{self.assessment_module.code}。"})
        if self.source_document_id:
            from assessments.models import AssessmentDocument

            if self.source_document.document_type != AssessmentDocument.DocumentType.MARKING_SCHEME:
                raise ValidationError({"source_document": "评分方案来源资料必须是评分表。"})
            if self.source_document.module_id != self.assessment_module_id:
                raise ValidationError({"source_document": "来源评分表必须属于当前评测模块。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

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
        self.clean()
        if self.is_default:
            type(self).objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        alias = f" ({self.alias})" if self.alias else ""
        return f"{self.display_name}{alias}"


class ScoringSchemeImport(models.Model):
    class Status(models.TextChoices):
        PARSED = "parsed", "已解析"
        CONFIRMED = "confirmed", "已确认"

    assessment_module = models.ForeignKey(
        "assessments.AssessmentModule",
        verbose_name="评测模块",
        on_delete=models.PROTECT,
        related_name="scoring_scheme_imports",
    )
    source_document = models.ForeignKey(
        "assessments.AssessmentDocument",
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


class ScoringResult(models.Model):
    class Source(models.TextChoices):
        ONLINE = "online", "在线评分"
        EXCEL_IMPORT = "excel_import", "Excel 导入"
        CMP_IMPORT = "cmp_import", "CMP 导入"
        MANUAL = "manual", "人工录入"

    participant = models.ForeignKey(
        "assessments.AssessmentParticipant",
        verbose_name="评测参与人员",
        on_delete=models.CASCADE,
        related_name="scoring_results",
    )
    aspect = models.ForeignKey(ScoringAspect, verbose_name="评分点", on_delete=models.PROTECT, related_name="results")
    score_awarded = models.DecimalField(
        "得分",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    source = models.CharField("来源", max_length=20, choices=Source.choices, default=Source.MANUAL)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="录入人",
        on_delete=models.SET_NULL,
        related_name="entered_scoring_results",
        null=True,
        blank=True,
    )
    entered_at = models.DateTimeField("录入时间", default=timezone.now)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="最后修改人",
        on_delete=models.SET_NULL,
        related_name="updated_scoring_results",
        null=True,
        blank=True,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="确认人",
        on_delete=models.SET_NULL,
        related_name="confirmed_scoring_results",
        null=True,
        blank=True,
    )
    confirmed_at = models.DateTimeField("确认时间", null=True, blank=True)
    evidence = models.TextField("证据摘要", blank=True)
    raw_payload = models.JSONField("原始结果", default=dict, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "评分结果"
        verbose_name_plural = "评分结果"
        ordering = ["participant", "aspect__order", "pk"]
        permissions = [("view_all_scoringresult", "查看全部评分结果")]
        constraints = [
            models.UniqueConstraint(fields=["participant", "aspect"], name="uniq_scoring_result"),
            models.CheckConstraint(condition=Q(score_awarded__gte=0), name="scoring_result_score_nonnegative"),
            models.CheckConstraint(
                condition=(Q(confirmed_by__isnull=True) & Q(confirmed_at__isnull=True))
                | (Q(confirmed_by__isnull=False) & Q(confirmed_at__isnull=False)),
                name="scoring_result_confirmation_pair",
            ),
        ]

    def clean(self):
        super().clean()
        if self.participant_id and self.aspect_id:
            assessment_id = self.aspect.scheme.assessment_module.assessment_id
            if self.participant.assessment_id != assessment_id:
                raise ValidationError({"participant": "参与人员必须属于评分方案对应的竞赛或考核。"})
            from assessments.models import CompetitionRole

            if self.participant.role.category != CompetitionRole.Category.COMPETITOR:
                raise ValidationError({"participant": "只有选手类参与人员可以产生评分结果。"})
        if self.aspect_id and self.score_awarded > self.aspect.max_mark:
            raise ValidationError({"score_awarded": f"得分不能超过评分点分值 {self.aspect.max_mark}。"})
        if bool(self.confirmed_by_id) != bool(self.confirmed_at):
            raise ValidationError("确认人和确认时间必须同时填写或同时留空。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.participant} / {self.aspect}: {self.score_awarded}"


class ScoringResultRevision(models.Model):
    scoring_result = models.ForeignKey(
        ScoringResult,
        verbose_name="评分结果",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    old_score = models.DecimalField("原得分", max_digits=8, decimal_places=2)
    new_score = models.DecimalField("新得分", max_digits=8, decimal_places=2)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="修改人",
        on_delete=models.SET_NULL,
        related_name="scoring_result_revisions",
        null=True,
        blank=True,
    )
    changed_at = models.DateTimeField("修改时间", auto_now_add=True)
    reason = models.CharField("修改原因", max_length=255, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "评分修改记录"
        ordering = ["-changed_at", "-pk"]
        default_permissions = ("view",)

    def __str__(self):
        return f"{self.scoring_result}：{self.old_score} → {self.new_score}"


class ScoringResultImport(models.Model):
    scheme = models.ForeignKey(
        ScoringScheme, verbose_name="评分方案", on_delete=models.PROTECT, related_name="result_imports"
    )
    source_document = models.ForeignKey(
        "assessments.AssessmentDocument",
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

    def clean(self):
        super().clean()
        if not self.source_document_id or not self.scheme_id:
            return

        from assessments.models import AssessmentDocument

        if self.source_document.document_type != AssessmentDocument.DocumentType.RESULT_FILE:
            raise ValidationError({"source_document": "结果包导入来源资料必须是成绩或结果文件。"})
        if self.source_document.module_id != self.scheme.assessment_module_id:
            raise ValidationError({"source_document": "来源结果文件必须属于评分方案对应的评测模块。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.scheme} / {self.source_document.filename}"


# Create your models here.
