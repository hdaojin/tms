from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


CONFIDENCE_VALIDATORS = [MinValueValidator(0.0), MaxValueValidator(1.0)]


class KnowledgeEvidence(models.Model):
    class SourceType(models.TextChoices):
        EXAM_REQUIREMENT = "exam_requirement", "试题要求"
        SCORING_ASPECT = "scoring_aspect", "评分点"
        MARKING_STANDARD = "marking_standard", "评分标准条目"
        SCRIPT_CHECK = "script_check", "评分脚本检查项"
        CMP_RESULT_ITEM = "cmp_result_item", "CMP 回传评分项"
        MANUAL = "manual", "教练手工补充考点"
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
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已拒绝"

    skill_project = models.ForeignKey(
        "standards.SkillProject",
        verbose_name="技能项目",
        on_delete=models.PROTECT,
        related_name="knowledge_evidences",
    )
    event_module = models.ForeignKey(
        "events.EventModule",
        verbose_name="事件模块",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_evidences",
    )
    capability_domain = models.ForeignKey(
        "standards.CapabilityDomain",
        verbose_name="能力领域",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_evidences",
    )
    source_type = models.CharField("来源类型", max_length=40, choices=SourceType.choices)
    source_content_type = models.ForeignKey(
        ContentType,
        verbose_name="来源对象类型",
        on_delete=models.SET_NULL,
        related_name="knowledge_evidences",
        null=True,
        blank=True,
    )
    source_object_id = models.PositiveBigIntegerField("来源对象 ID", null=True, blank=True)
    source_object = GenericForeignKey("source_content_type", "source_object_id")
    title = models.CharField("标题", max_length=200)
    original_text = models.TextField("原始文本", blank=True)
    normalized_text = models.TextField("规范化文本", blank=True)
    estimated_mark = models.DecimalField(
        "分值估计",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    estimated_difficulty = models.PositiveSmallIntegerField(
        "难度估计",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    evidence_level = models.CharField("证据等级", max_length=50, blank=True)
    extraction_source = models.CharField(
        "提取来源",
        max_length=20,
        choices=ExtractionSource.choices,
        default=ExtractionSource.MANUAL,
    )
    confidence = models.FloatField("置信度", default=1.0, validators=CONFIDENCE_VALIDATORS)
    review_status = models.CharField(
        "审核状态",
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.DRAFT,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审核人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_knowledge_evidences",
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
        related_name="created_knowledge_evidences",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "考点证据"
        verbose_name_plural = "考点证据"
        ordering = ["-created_at", "-pk"]

    def clean(self):
        super().clean()
        if self.event_module_id and self.skill_project_id != self.event_module.event.skill_project_id:
            raise ValidationError({"skill_project": "技能项目必须与事件模块所属技能项目一致。"})
        if self.capability_domain_id and self.skill_project_id != self.capability_domain.skill_project_id:
            raise ValidationError({"capability_domain": "能力领域必须属于当前技能项目。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def primary_skill_mapping(self):
        return self.skill_mappings.filter(is_primary=True).select_related("skill_node").first()

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


class KnowledgeEvidenceSkillMap(models.Model):
    class MappingSource(models.TextChoices):
        MANUAL = "manual", "人工"
        AI = "ai", "AI"
        IMPORTED = "imported", "导入"
        PARSER = "parser", "解析器"

    evidence = models.ForeignKey(
        KnowledgeEvidence,
        verbose_name="考点证据",
        on_delete=models.CASCADE,
        related_name="skill_mappings",
    )
    skill_node = models.ForeignKey(
        "standards.SkillNode",
        verbose_name="技能点",
        on_delete=models.PROTECT,
        related_name="knowledge_evidence_mappings",
    )
    is_primary = models.BooleanField("主技能点", default=False)
    weight = models.DecimalField(
        "权重",
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    mapping_source = models.CharField("映射来源", max_length=20, choices=MappingSource.choices, default=MappingSource.MANUAL)
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
        related_name="reviewed_knowledge_skill_mappings",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "考点技能映射"
        verbose_name_plural = "考点技能映射"
        ordering = ["evidence", "-is_primary", "skill_node__order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["evidence", "skill_node"],
                name="uniq_knowledge_evidence_skill_node",
            ),
            models.UniqueConstraint(
                fields=["evidence"],
                condition=Q(is_primary=True),
                name="uniq_knowledge_primary_skill_per_evidence",
            ),
        ]

    def clean(self):
        super().clean()
        from standards.models import SkillNode

        if self.skill_node_id and self.skill_node.node_type != SkillNode.NodeType.SKILL:
            raise ValidationError({"skill_node": "考点证据只能映射到标准技能点。"})
        if self.skill_node_id and not self.skill_node.is_active:
            raise ValidationError({"skill_node": "只能映射到启用状态的标准技能点。"})
        if self.skill_node_id and not self.skill_node.tree_version.is_current:
            raise ValidationError({"skill_node": "只能映射到当前技能树版本中的标准技能点。"})
        if self.evidence_id and self.skill_node_id:
            if self.evidence.skill_project_id != self.skill_node.tree_version.skill_project_id:
                raise ValidationError({"skill_node": "技能点必须属于考点证据对应的技能项目。"})
            if self.evidence.capability_domain_id and self.evidence.capability_domain_id != self.skill_node.capability_domain_id:
                raise ValidationError({"skill_node": "技能点能力领域必须与考点证据能力领域一致。"})
        if self.is_primary and self.evidence_id:
            existing_primary = type(self).objects.filter(evidence_id=self.evidence_id, is_primary=True).exclude(pk=self.pk)
            if existing_primary.exists():
                raise ValidationError({"is_primary": "同一个考点证据只能设置一个主技能点映射。"})

    def save(self, *args, **kwargs):
        self.clean()
        if self.review_status == KnowledgeEvidence.ReviewStatus.APPROVED and not self.reviewed_at:
            self.reviewed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.evidence} -> {self.skill_node}"

# Create your models here.
