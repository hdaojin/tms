from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


CONFIDENCE_VALIDATORS = [MinValueValidator(0.0), MaxValueValidator(1.0)]


class KnowledgeEvidence(models.Model):
    class SourceType(models.TextChoices):
        SCORING_ASPECT = "scoring_aspect", "评分点"
        TEST_PROJECT = "test_project", "试题"
        MARKING_STANDARD = "marking_standard", "评分标准"
        SCRIPT_CHECK = "script_check", "评分脚本检查项"
        CMP_RESULT_ITEM = "cmp_result_item", "CMP 结果项"
        MANUAL = "manual", "人工补充"
        OTHER = "other", "其他"

    class ExtractionSource(models.TextChoices):
        MANUAL = "manual", "人工"
        PARSER = "parser", "解析器"
        AI = "ai", "AI"
        CMP = "cmp", "CMP"
        IMPORTED = "imported", "导入"

    class ReviewStatus(models.TextChoices):
        DRAFT = "draft", "草稿"
        PENDING = "pending", "待审核"
        APPROVED = "approved", "已批准"
        REJECTED = "rejected", "已拒绝"

    skill_project = models.ForeignKey(
        "standards.SkillProject", verbose_name="技能项目", on_delete=models.PROTECT, related_name="knowledge_evidences"
    )
    assessment_module = models.ForeignKey(
        "assessments.AssessmentModule",
        verbose_name="评测模块",
        on_delete=models.PROTECT,
        related_name="evidences",
        null=True,
        blank=True,
    )
    source_type = models.CharField("来源类型", max_length=30, choices=SourceType.choices)
    scoring_aspect = models.OneToOneField(
        "scoring.ScoringAspect",
        verbose_name="来源评分点",
        on_delete=models.PROTECT,
        related_name="knowledge_evidence",
        null=True,
        blank=True,
    )
    source_document = models.ForeignKey(
        "assessments.AssessmentDocument",
        verbose_name="来源资料",
        on_delete=models.PROTECT,
        related_name="evidences",
        null=True,
        blank=True,
    )
    title = models.CharField("标题", max_length=200)
    original_text = models.TextField("原始文本", blank=True)
    normalized_text = models.TextField("规范文本", blank=True)
    source_location = models.CharField("来源位置", max_length=200, blank=True)
    estimated_mark = models.DecimalField(
        "估计分值", max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    estimated_difficulty = models.PositiveSmallIntegerField(
        "难度估计", null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    evidence_level = models.CharField("证据等级", max_length=50, blank=True)
    extraction_source = models.CharField(
        "提取来源", max_length=20, choices=ExtractionSource.choices, default=ExtractionSource.MANUAL
    )
    confidence = models.FloatField("置信度", default=1.0, validators=CONFIDENCE_VALIDATORS)
    review_status = models.CharField(
        "审核状态", max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审核人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_evidences",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    review_note = models.TextField("审核备注", blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_evidences",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "考点证据"
        ordering = ["-created_at", "-pk"]

    def clean(self):
        super().clean()
        project_ids = {self.skill_project_id}
        if self.assessment_module_id:
            project_ids.add(self.assessment_module.assessment.skill_project_id)
        if self.source_document_id:
            project_ids.add(self.source_document.assessment.skill_project_id)
            if self.assessment_module_id and self.source_document.module_id not in {None, self.assessment_module_id}:
                raise ValidationError({"source_document": "来源资料必须属于当前评测模块或评测公共资料。"})
        if self.scoring_aspect_id:
            project_ids.add(self.scoring_aspect.scheme.assessment_module.assessment.skill_project_id)
            if self.assessment_module_id != self.scoring_aspect.scheme.assessment_module_id:
                raise ValidationError({"scoring_aspect": "来源评分点必须属于当前评测模块。"})
        if len(project_ids - {None}) > 1:
            raise ValidationError("考点证据的来源对象必须属于同一技能项目。")
        if self.source_type == self.SourceType.SCORING_ASPECT and not self.scoring_aspect_id:
            raise ValidationError({"scoring_aspect": "评分点来源的考点证据必须关联评分点。"})
        if (
            self.source_type in {self.SourceType.TEST_PROJECT, self.SourceType.MARKING_STANDARD}
            and not self.source_document_id
        ):
            raise ValidationError({"source_document": "当前来源类型必须关联原始资料。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def primary_skill_mapping(self):
        return (
            self.skill_mappings.filter(is_primary=True, review_status=self.ReviewStatus.APPROVED)
            .select_related("skill")
            .first()
        )

    def approve(self, user=None, note=""):
        self.review_status = self.ReviewStatus.APPROVED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        if note:
            self.review_note = note
        self.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

    def reject(self, user=None, note=""):
        if not note:
            raise ValidationError({"review_note": "拒绝考点证据时必须填写审核备注。"})
        self.review_status = self.ReviewStatus.REJECTED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.review_note = note
        self.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

    def __str__(self):
        return self.title


class EvidenceSkillMap(models.Model):
    class MappingSource(models.TextChoices):
        MANUAL = "manual", "人工"
        AI = "ai", "AI"
        IMPORTED = "imported", "导入"
        PARSER = "parser", "解析器"

    evidence = models.ForeignKey(
        KnowledgeEvidence, verbose_name="考点证据", on_delete=models.CASCADE, related_name="skill_mappings"
    )
    skill = models.ForeignKey(
        "standards.Skill", verbose_name="技能", on_delete=models.PROTECT, related_name="evidence_mappings"
    )
    is_primary = models.BooleanField("主技能", default=False)
    weight = models.DecimalField(
        "权重",
        max_digits=5,
        decimal_places=4,
        default=Decimal("1.0000"),
        validators=[MinValueValidator(Decimal("0.0001")), MaxValueValidator(Decimal("1.0000"))],
    )
    mapping_source = models.CharField(
        "映射来源", max_length=20, choices=MappingSource.choices, default=MappingSource.MANUAL
    )
    confidence = models.FloatField("置信度", default=1.0, validators=CONFIDENCE_VALIDATORS)
    reason = models.TextField("理由", blank=True)
    review_status = models.CharField(
        "审核状态",
        max_length=20,
        choices=KnowledgeEvidence.ReviewStatus.choices,
        default=KnowledgeEvidence.ReviewStatus.DRAFT,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审核人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_evidence_skill_mappings",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "考点技能映射"
        ordering = ["evidence", "-is_primary", "skill__order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["evidence", "skill"], name="uniq_evidence_skill"),
            models.UniqueConstraint(
                fields=["evidence"], condition=Q(is_primary=True), name="uniq_primary_skill_per_evidence"
            ),
        ]

    def clean(self):
        super().clean()
        if self.skill_id and not self.skill.is_active:
            raise ValidationError({"skill": "只能映射到启用状态的技能。"})
        if self.evidence_id and self.skill_id and self.evidence.skill_project_id != self.skill.skill_project_id:
            raise ValidationError({"skill": "技能必须属于考点证据对应的技能项目。"})
        if self.review_status == KnowledgeEvidence.ReviewStatus.APPROVED and self.evidence_id:
            total = type(self).objects.filter(
                evidence_id=self.evidence_id, review_status=KnowledgeEvidence.ReviewStatus.APPROVED
            ).exclude(pk=self.pk).aggregate(total=Sum("weight"))["total"] or Decimal("0")
            if total + self.weight > Decimal("1.0000"):
                raise ValidationError({"weight": "同一考点证据的已批准映射权重合计不能超过 1。"})

    def save(self, *args, **kwargs):
        self.clean()
        if self.review_status == KnowledgeEvidence.ReviewStatus.APPROVED and not self.reviewed_at:
            self.reviewed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.evidence} -> {self.skill}"
