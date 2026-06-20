from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ExamPaper(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        STRUCTURED = "structured", "已结构化"
        ARCHIVED = "archived", "已归档"

    event_module = models.ForeignKey(
        "events.EventModule",
        verbose_name="事件模块",
        on_delete=models.PROTECT,
        related_name="exam_papers",
    )
    source_asset = models.ForeignKey(
        "archives.ArchiveAsset",
        verbose_name="试题文件",
        on_delete=models.PROTECT,
        related_name="exam_papers",
        null=True,
        blank=True,
    )
    title = models.CharField("标题", max_length=200)
    version = models.CharField("版本", max_length=50, blank=True)
    language = models.CharField("语言", max_length=50, default="zh-hans")
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_exam_papers",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "试题"
        verbose_name_plural = "试题"
        ordering = ["-created_at", "-pk"]

    @property
    def skill_project(self):
        return self.event_module.event.skill_project

    def __str__(self):
        return self.title


class ExamRequirement(models.Model):
    class RequirementType(models.TextChoices):
        EXPLICIT = "explicit", "显性要求"
        IMPLICIT = "implicit", "隐含考点"
        CONSTRAINT = "constraint", "约束条件"
        OTHER = "other", "其他"

    class ExtractionSource(models.TextChoices):
        MANUAL = "manual", "人工"
        PARSER = "parser", "解析器"
        AI = "ai", "AI"

    paper = models.ForeignKey(ExamPaper, verbose_name="试题", on_delete=models.CASCADE, related_name="requirements")
    capability_domain = models.ForeignKey(
        "standards.CapabilityDomain",
        verbose_name="能力领域",
        on_delete=models.SET_NULL,
        related_name="exam_requirements",
        null=True,
        blank=True,
    )
    code = models.CharField("要求编号", max_length=80)
    title = models.CharField("标题", max_length=200)
    original_text = models.TextField("原始文本", blank=True)
    normalized_text = models.TextField("规范化文本", blank=True)
    requirement_type = models.CharField("要求类型", max_length=20, choices=RequirementType.choices, default=RequirementType.EXPLICIT)
    source_location = models.CharField("来源位置", max_length=150, blank=True)
    estimated_difficulty = models.PositiveSmallIntegerField(
        "难度估计",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    is_explicitly_marked = models.BooleanField("评分表明确计分", default=False)
    extraction_source = models.CharField("提取来源", max_length=20, choices=ExtractionSource.choices, default=ExtractionSource.MANUAL)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    knowledge_evidences = GenericRelation(
        "knowledge.KnowledgeEvidence",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
        related_query_name="exam_requirement",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "试题要求"
        verbose_name_plural = "试题要求"
        ordering = ["paper", "code", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["paper", "code"], name="uniq_examrequirement_paper_code"),
        ]

    def clean(self):
        super().clean()
        if self.capability_domain_id and self.paper_id:
            if self.capability_domain.skill_project_id != self.paper.event_module.event.skill_project_id:
                raise ValidationError({"capability_domain": "能力领域必须属于试题对应的技能项目。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.title}"

# Create your models here.
