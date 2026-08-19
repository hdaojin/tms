from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from core.uploads import (
    ASSESSMENT_DOCUMENT_UPLOAD_SPEC,
    PrivateMediaStorage,
    UploadSignatureValidator,
    compute_file_sha256,
)


assessment_storage = PrivateMediaStorage("assessments")


def assessment_document_upload_path(instance, filename):
    module_code = instance.module.code if instance.module_id else "general"
    return str(Path(instance.assessment.code, module_code, instance.document_type, Path(filename).name))


class AssessmentSeries(models.Model):
    code = models.CharField("系列代码", max_length=50, unique=True)
    name = models.CharField("系列名称", max_length=120)
    description = models.TextField("描述", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "竞赛与考核系列"
        ordering = ["order", "code"]

    def __str__(self):
        return self.name


class AssessmentLevel(models.Model):
    code = models.CharField("级别代码", max_length=50, unique=True)
    name = models.CharField("级别名称", max_length=120)
    weight = models.DecimalField(
        "历史统计权重", max_digits=6, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(0)]
    )
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "竞赛与考核级别"
        ordering = ["order", "code"]

    def __str__(self):
        return self.name


class Assessment(models.Model):
    class Type(models.TextChoices):
        COMPETITION = "competition", "正式竞赛"
        SELECTION = "selection", "选拔赛"
        EXCHANGE = "exchange", "交流赛"
        MOCK = "mock", "模拟赛"
        TRAINING_ASSESSMENT = "training_assessment", "训练考核"
        TRAINING_TEST = "training_test", "训练测试"
        OTHER = "other", "其他"

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"
        ACTIVE = "active", "进行中"
        COMPLETED = "completed", "已完成"
        ARCHIVED = "archived", "已归档"
        CANCELLED = "cancelled", "已取消"

    skill_project = models.ForeignKey(
        "standards.SkillProject", verbose_name="技能项目", on_delete=models.PROTECT, related_name="assessments"
    )
    series = models.ForeignKey(
        AssessmentSeries,
        verbose_name="系列",
        on_delete=models.PROTECT,
        related_name="assessments",
        null=True,
        blank=True,
    )
    level = models.ForeignKey(
        AssessmentLevel,
        verbose_name="级别",
        on_delete=models.PROTECT,
        related_name="assessments",
        null=True,
        blank=True,
    )
    training_cycle = models.ForeignKey(
        "training.TrainingCycle",
        verbose_name="训练周期",
        on_delete=models.PROTECT,
        related_name="assessments",
        null=True,
        blank=True,
    )
    assessment_type = models.CharField("类型", max_length=30, choices=Type.choices)
    name = models.CharField("名称", max_length=180)
    code = models.CharField("代码", max_length=80, unique=True)
    start_date = models.DateField("开始日期")
    end_date = models.DateField("结束日期", null=True, blank=True)
    location = models.CharField("地点", max_length=200, blank=True)
    description = models.TextField("描述", blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_assessments",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "竞赛与考核"
        ordering = ["-start_date", "code"]

    def clean(self):
        super().clean()
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "结束日期不能早于开始日期。"})
        if (
            self.training_cycle_id
            and self.skill_project_id
            and self.training_cycle.skill_project_id != self.skill_project_id
        ):
            raise ValidationError({"training_cycle": "训练周期必须属于当前技能项目。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class AssessmentModule(models.Model):
    assessment = models.ForeignKey(
        Assessment, verbose_name="竞赛与考核", on_delete=models.CASCADE, related_name="modules"
    )
    code = models.CharField("模块代码", max_length=50)
    name = models.CharField("模块名称", max_length=150)
    description = models.TextField("描述", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    total_mark = models.DecimalField(
        "总分", max_digits=8, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0)]
    )
    duration_minutes = models.PositiveIntegerField("时长（分钟）", null=True, blank=True)
    counts_towards_ranking = models.BooleanField("计入排名", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "评测模块"
        ordering = ["assessment", "order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "code"], name="uniq_assessmentmodule_assessment_code")
        ]

    def __str__(self):
        return f"{self.assessment.code} / {self.code} - {self.name}"


class AssessmentModuleDomain(models.Model):
    class Role(models.TextChoices):
        PRIMARY = "primary", "主要领域"
        RELATED = "related", "关联领域"

    assessment_module = models.ForeignKey(
        AssessmentModule, verbose_name="评测模块", on_delete=models.CASCADE, related_name="domain_mappings"
    )
    technical_domain = models.ForeignKey(
        "standards.TechnicalDomain",
        verbose_name="技术领域",
        on_delete=models.PROTECT,
        related_name="assessment_module_mappings",
    )
    role = models.CharField("角色", max_length=20, choices=Role.choices, default=Role.RELATED)
    note = models.TextField("说明", blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "评测模块技术领域"
        constraints = [
            models.UniqueConstraint(
                fields=["assessment_module", "technical_domain"], name="uniq_assessmentmodule_domain"
            ),
            models.UniqueConstraint(
                fields=["assessment_module"],
                condition=Q(role="primary"),
                name="uniq_primary_domain_per_assessmentmodule",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.assessment_module_id
            and self.technical_domain_id
            and self.assessment_module.assessment.skill_project_id != self.technical_domain.skill_project_id
        ):
            raise ValidationError({"technical_domain": "技术领域必须属于评测对应的技能项目。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class AssessmentModuleCoach(models.Model):
    class Role(models.TextChoices):
        PRIMARY = "primary", "主教练"
        COLLABORATOR = "collaborator", "协作教练"

    assessment_module = models.ForeignKey(
        AssessmentModule, verbose_name="评测模块", on_delete=models.CASCADE, related_name="coach_assignments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="教练",
        on_delete=models.PROTECT,
        related_name="assessment_module_assignments",
    )
    role = models.CharField("角色", max_length=20, choices=Role.choices, default=Role.COLLABORATOR)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "评测模块教练"
        constraints = [
            models.UniqueConstraint(fields=["assessment_module", "user"], name="uniq_assessmentmodule_coach"),
            models.UniqueConstraint(
                fields=["assessment_module"],
                condition=Q(role="primary"),
                name="uniq_primary_coach_per_assessmentmodule",
            ),
        ]


class AssessmentParticipant(models.Model):
    class Role(models.TextChoices):
        COMPETITOR = "competitor", "选手"
        EXPERT = "expert", "专家"
        COACH = "coach", "教练"
        STAFF = "staff", "工作人员"
        OBSERVER = "observer", "观察员"
        OTHER = "other", "其他"

    assessment = models.ForeignKey(
        Assessment, verbose_name="竞赛与考核", on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="关联用户",
        on_delete=models.PROTECT,
        related_name="assessment_participations",
        null=True,
        blank=True,
    )
    external_code = models.CharField("外部代码", max_length=100, blank=True)
    display_name = models.CharField("显示名称", max_length=150)
    role = models.CharField("角色", max_length=20, choices=Role.choices, default=Role.COMPETITOR)
    organization = models.CharField("单位", max_length=200, blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "评测参与人员"
        ordering = ["assessment", "role", "display_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "user"], condition=Q(user__isnull=False), name="uniq_assessmentparticipant_user"
            ),
            models.UniqueConstraint(
                fields=["assessment", "external_code"],
                condition=~Q(external_code=""),
                name="uniq_assessmentparticipant_external",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.user_id and not self.external_code:
            raise ValidationError("参与人员必须关联系统用户或填写外部代码。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class AssessmentResultSummary(models.Model):
    assessment = models.ForeignKey(
        Assessment, verbose_name="竞赛与考核", on_delete=models.CASCADE, related_name="result_summaries"
    )
    participant = models.OneToOneField(
        AssessmentParticipant, verbose_name="参与人员", on_delete=models.CASCADE, related_name="result_summary"
    )
    total_score = models.DecimalField("总分", max_digits=10, decimal_places=2, null=True, blank=True)
    rank = models.PositiveIntegerField("名次", null=True, blank=True)
    award = models.CharField("奖项", max_length=100, blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "评测结果摘要"

    def clean(self):
        super().clean()
        if self.participant_id and self.assessment_id and self.participant.assessment_id != self.assessment_id:
            raise ValidationError({"participant": "参与人员必须属于当前评测。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class AssessmentDocument(models.Model):
    class DocumentType(models.TextChoices):
        TEST_PROJECT = "test_project", "试题"
        MARKING_SCHEME = "marking_scheme", "评分表"
        MARKING_STANDARD = "marking_standard", "评分标准"
        SCORING_SCRIPT = "scoring_script", "评分脚本"
        RESULT_FILE = "result_file", "成绩或结果文件"
        ATTACHMENT = "attachment", "其他附件"

    assessment = models.ForeignKey(
        Assessment, verbose_name="竞赛与考核", on_delete=models.CASCADE, related_name="documents"
    )
    module = models.ForeignKey(
        AssessmentModule,
        verbose_name="评测模块",
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    document_type = models.CharField("资料类型", max_length=30, choices=DocumentType.choices)
    title = models.CharField("标题", max_length=255)
    description = models.TextField("描述", blank=True)
    file = models.FileField(
        "文件",
        storage=assessment_storage,
        upload_to=assessment_document_upload_path,
        validators=[*ASSESSMENT_DOCUMENT_UPLOAD_SPEC.validators(), UploadSignatureValidator()],
        help_text=ASSESSMENT_DOCUMENT_UPLOAD_SPEC.help_text(),
    )
    original_filename = models.CharField("原始文件名", max_length=255)
    file_sha256 = models.CharField("SHA256", max_length=64, editable=False)
    version = models.CharField("版本", max_length=50, blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传者",
        on_delete=models.PROTECT,
        related_name="uploaded_assessment_documents",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "评测资料"
        ordering = ["assessment", "module_id", "document_type", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "module", "document_type", "file_sha256"],
                condition=Q(module__isnull=False),
                name="uniq_assessment_document_module_hash",
            ),
            models.UniqueConstraint(
                fields=["assessment", "document_type", "file_sha256"],
                condition=Q(module__isnull=True),
                name="uniq_assessment_document_general_hash",
            ),
        ]

    def clean(self):
        super().clean()
        if self.module_id and self.assessment_id and self.module.assessment_id != self.assessment_id:
            raise ValidationError({"module": "评测模块必须属于当前竞赛与考核。"})

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            self.original_filename = Path(self.file.name).name
        if self.file and (not self.file_sha256 or not self.file._committed):
            self.file_sha256 = compute_file_sha256(self.file)
        self.clean()
        super().save(*args, **kwargs)

    @property
    def filename(self):
        return self.original_filename or Path(self.file.name).name

    def __str__(self):
        return self.title
