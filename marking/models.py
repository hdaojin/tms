from __future__ import annotations

from decimal import Decimal
from pathlib import PurePosixPath

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.uploads import MARKING_RESULT_PACKAGE_UPLOAD_SPEC, MARKING_WORKBOOK_UPLOAD_SPEC, PrivateMediaStorage
from core.utils.signals import register_file_cleanup_signals


marking_storage = PrivateMediaStorage("marking")


def marking_scheme_upload_path(instance, filename):
    uploaded_at = instance.uploaded_at or timezone.now()
    return str(PurePosixPath("schemes") / uploaded_at.strftime("%Y/%m") / filename)


def result_package_upload_path(instance, filename):
    imported_at = instance.imported_at or timezone.now()
    return str(PurePosixPath("result-packages") / imported_at.strftime("%Y/%m") / filename)


def _target_module_code(target):
    if target is None:
        return ""
    if target.__class__.__name__ == "CompetitionModule":
        return target.code
    if target.__class__.__name__ == "AssessmentModule":
        return target.module.code
    return ""


def _target_standard_module(target):
    if target is None:
        return None
    if target.__class__.__name__ == "CompetitionModule":
        return target.primary_standard_module
    if target.__class__.__name__ == "AssessmentModule":
        return target.module
    return None


class MarkingSchemeImport(models.Model):
    class Status(models.TextChoices):
        IMPORTED = "imported", "已导入"
        FAILED = "failed", "导入失败"

    file = models.FileField(
        "评分表文件",
        storage=marking_storage,
        upload_to=marking_scheme_upload_path,
        validators=MARKING_WORKBOOK_UPLOAD_SPEC.validators(),
        help_text=MARKING_WORKBOOK_UPLOAD_SPEC.help_text("上传新版单模块评分表"),
    )
    original_filename = models.CharField("原始文件名", max_length=255, blank=True)
    file_sha256 = models.CharField("文件 SHA256", max_length=64, db_index=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.IMPORTED)
    parser_version = models.CharField("解析器版本", max_length=30)
    parse_summary = models.JSONField("解析摘要", default=dict, blank=True)
    target_content_type = models.ForeignKey(
        ContentType,
        verbose_name="绑定对象类型",
        on_delete=models.PROTECT,
        related_name="marking_scheme_imports",
    )
    target_object_id = models.PositiveBigIntegerField("绑定对象 ID")
    target_object = GenericForeignKey("target_content_type", "target_object_id")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传者",
        on_delete=models.SET_NULL,
        related_name="marking_scheme_imports",
        null=True,
        blank=True,
    )
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        verbose_name = "评分表导入"
        verbose_name_plural = "评分表导入"
        ordering = ["-uploaded_at", "-pk"]

    def __str__(self):
        return self.original_filename or PurePosixPath(self.file.name).name


class MarkingScheme(models.Model):
    source_import = models.OneToOneField(
        MarkingSchemeImport,
        verbose_name="来源导入",
        on_delete=models.PROTECT,
        related_name="scheme",
    )
    standard_module = models.ForeignKey(
        "competition_standards.StandardModule",
        verbose_name="标准模块",
        on_delete=models.PROTECT,
        related_name="marking_schemes",
    )
    target_content_type = models.ForeignKey(
        ContentType,
        verbose_name="绑定对象类型",
        on_delete=models.PROTECT,
        related_name="marking_schemes",
    )
    target_object_id = models.PositiveBigIntegerField("绑定对象 ID")
    target_object = GenericForeignKey("target_content_type", "target_object_id")
    title = models.CharField("标题", max_length=255)
    module_code = models.CharField("模块编号", max_length=50)
    module_name = models.CharField("模块名称", max_length=100)
    total_mark = models.DecimalField("总分", max_digits=8, decimal_places=2)
    parser_version = models.CharField("解析器版本", max_length=30)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "评分方案"
        verbose_name_plural = "评分方案"
        ordering = ["-created_at", "module_code", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["target_content_type", "target_object_id", "module_code"],
                name="uniq_marking_scheme_target_module",
            ),
        ]

    def clean(self):
        super().clean()
        target = self.target_object
        if target is None:
            return
        target_code = _target_module_code(target)
        if self.module_code and target_code and self.module_code != target_code:
            raise ValidationError({"module_code": f"评分表模块编号必须与绑定模块一致：{target_code}。"})
        standard_module = _target_standard_module(target)
        if standard_module is None:
            raise ValidationError("竞赛官方模块必须先配置主标准模块映射后才能导入评分表。")
        if self.standard_module_id and self.standard_module_id != standard_module.pk:
            raise ValidationError({"standard_module": "评分方案标准模块必须与绑定对象一致。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.module_code} - {self.module_name}"


class MarkingSubCriterion(models.Model):
    scheme = models.ForeignKey(MarkingScheme, verbose_name="评分方案", on_delete=models.CASCADE, related_name="subcriteria")
    code = models.CharField("子评分项编号", max_length=30)
    name = models.CharField("子评分项名称或描述", max_length=300)
    day_of_marking = models.CharField("评分日", max_length=50)
    sort_order = models.PositiveIntegerField("显示顺序", default=0)

    class Meta:
        verbose_name = "评分子项"
        verbose_name_plural = "评分子项"
        ordering = ["scheme", "sort_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["scheme", "code"], name="uniq_marking_subcriterion"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class MarkingAspect(models.Model):
    class AspectType(models.TextChoices):
        MEASUREMENT = "M", "测量"
        JUDGEMENT = "J", "评价"

    scheme = models.ForeignKey(MarkingScheme, verbose_name="评分方案", on_delete=models.CASCADE, related_name="aspects")
    subcriterion = models.ForeignKey(
        MarkingSubCriterion,
        verbose_name="评分子项",
        on_delete=models.PROTECT,
        related_name="aspects",
    )
    code = models.CharField("评分点编号", max_length=50)
    aspect_type = models.CharField("评分类型", max_length=1, choices=AspectType.choices)
    description = models.TextField("评分点")
    command = models.TextField("命令或操作", blank=True)
    requirement = models.TextField("期望结果", blank=True)
    wsos_section = models.CharField("WSOS 章节", max_length=50, blank=True)
    calculation_row = models.CharField("计算行", max_length=100, blank=True)
    max_mark = models.DecimalField(
        "分值",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    source_row_number = models.PositiveIntegerField("来源行号")
    sort_order = models.PositiveIntegerField("显示顺序", default=0)

    class Meta:
        verbose_name = "评分点"
        verbose_name_plural = "评分点"
        ordering = ["scheme", "subcriterion__sort_order", "sort_order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["scheme", "code"], name="uniq_marking_aspect_code"),
            models.UniqueConstraint(fields=["scheme", "source_row_number"], name="uniq_marking_aspect_source_row"),
        ]

    def __str__(self):
        return f"{self.code} - {self.description}"


class JudgementOption(models.Model):
    aspect = models.ForeignKey(
        MarkingAspect,
        verbose_name="评价评分点",
        on_delete=models.CASCADE,
        related_name="judgement_options",
    )
    score_value = models.DecimalField("分档值", max_digits=6, decimal_places=2)
    description = models.TextField("分档说明")
    source_row_number = models.PositiveIntegerField("来源行号")
    sort_order = models.PositiveIntegerField("显示顺序", default=0)

    class Meta:
        verbose_name = "评价分档"
        verbose_name_plural = "评价分档"
        ordering = ["aspect", "sort_order", "score_value"]
        constraints = [
            models.UniqueConstraint(fields=["aspect", "score_value"], name="uniq_judgement_option"),
        ]

    def __str__(self):
        return f"{self.score_value} - {self.description}"


class MarkingAspectSkillNodeMap(models.Model):
    aspect = models.ForeignKey(
        MarkingAspect,
        verbose_name="评分点",
        on_delete=models.CASCADE,
        related_name="skill_node_mappings",
    )
    skill_node = models.ForeignKey(
        "skilltrees.SkillNode",
        verbose_name="技能节点",
        on_delete=models.CASCADE,
        related_name="marking_aspect_mappings",
    )
    is_primary = models.BooleanField("主技能", default=False)
    weight = models.DecimalField(
        "权重",
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    note = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = "评分点技能映射"
        verbose_name_plural = "评分点技能映射"
        ordering = ["aspect", "-is_primary", "skill_node__sort_order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["aspect", "skill_node"], name="uniq_marking_aspect_skillnode"),
            models.UniqueConstraint(
                fields=["aspect"],
                condition=Q(is_primary=True),
                name="uniq_primary_skillnode_per_aspect",
            ),
        ]

    def clean(self):
        super().clean()
        from skilltrees.models import SkillNode

        if self.skill_node_id and self.skill_node.node_type != SkillNode.NodeType.SKILL:
            raise ValidationError({"skill_node": "评分点只能归类到技能点类型的节点。"})
        if (
            self.aspect_id
            and self.skill_node_id
            and self.aspect.scheme.standard_module_id != self.skill_node.tree.module_id
        ):
            raise ValidationError({"skill_node": "技能节点必须属于评分方案对应的标准模块。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.aspect} -> {self.skill_node}"


class MarkingParticipant(models.Model):
    scheme = models.ForeignKey(MarkingScheme, verbose_name="评分方案", on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="关联用户",
        on_delete=models.PROTECT,
        related_name="marking_participations",
        null=True,
        blank=True,
    )
    competitor = models.ForeignKey(
        "competitions.Competitor",
        verbose_name="关联竞赛选手",
        on_delete=models.PROTECT,
        related_name="marking_participations",
        null=True,
        blank=True,
    )
    external_identifier = models.CharField("外部编号", max_length=100, blank=True)
    display_name = models.CharField("显示名称", max_length=200)
    organization = models.CharField("所属单位", max_length=200, blank=True)
    member_name = models.CharField("代表队", max_length=100, blank=True)
    snapshot = models.JSONField("参评对象快照", default=dict, blank=True)
    sort_order = models.PositiveIntegerField("显示顺序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "参评对象"
        verbose_name_plural = "参评对象"
        ordering = ["scheme", "sort_order", "display_name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["scheme", "user"], condition=Q(user__isnull=False), name="uniq_marking_participant_user"),
            models.UniqueConstraint(
                fields=["scheme", "competitor"],
                condition=Q(competitor__isnull=False),
                name="uniq_marking_participant_competitor",
            ),
            models.UniqueConstraint(
                fields=["scheme", "external_identifier"],
                condition=~Q(external_identifier=""),
                name="uniq_marking_participant_external",
            ),
        ]

    def clean(self):
        super().clean()
        identities = [bool(self.user_id), bool(self.competitor_id), bool(self.external_identifier)]
        if sum(identities) != 1:
            raise ValidationError("参评对象必须且只能绑定用户、竞赛选手或外部编号中的一种。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class MarkingResult(models.Model):
    class Source(models.TextChoices):
        CMP = "cmp", "CMP 导入"
        IMPORTED = "imported", "文件导入"
        MANUAL = "manual", "人工录入"

    participant = models.ForeignKey(
        MarkingParticipant,
        verbose_name="参评对象",
        on_delete=models.CASCADE,
        related_name="results",
    )
    aspect = models.ForeignKey(MarkingAspect, verbose_name="评分点", on_delete=models.PROTECT, related_name="results")
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
        ordering = ["participant", "aspect__sort_order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "aspect"], name="uniq_marking_result"),
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


class MarkingResultImport(models.Model):
    scheme = models.ForeignKey(MarkingScheme, verbose_name="评分方案", on_delete=models.PROTECT, related_name="result_imports")
    file = models.FileField(
        "JSON 结果包",
        storage=marking_storage,
        upload_to=result_package_upload_path,
        validators=MARKING_RESULT_PACKAGE_UPLOAD_SPEC.validators(),
        help_text=MARKING_RESULT_PACKAGE_UPLOAD_SPEC.help_text("上传 CMP 标准结果包"),
    )
    original_filename = models.CharField("原始文件名", max_length=255, blank=True)
    file_sha256 = models.CharField("文件 SHA256", max_length=64, db_index=True)
    summary = models.JSONField("导入摘要", default=dict, blank=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="导入者",
        on_delete=models.SET_NULL,
        related_name="marking_result_imports",
        null=True,
        blank=True,
    )
    imported_at = models.DateTimeField("导入时间", auto_now_add=True)

    class Meta:
        verbose_name = "结果包导入"
        verbose_name_plural = "结果包导入"
        ordering = ["-imported_at", "-pk"]

    def __str__(self):
        return self.original_filename or PurePosixPath(self.file.name).name


register_file_cleanup_signals(MarkingSchemeImport, file_field="file")
register_file_cleanup_signals(MarkingResultImport, file_field="file")
