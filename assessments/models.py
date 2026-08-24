from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from accounts.services.users import get_user_display_name
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


class CompetitionPerson(models.Model):
    name = models.CharField("姓名", max_length=150)
    organization = models.CharField("单位", max_length=200, blank=True)
    country_or_region = models.CharField("国家或地区", max_length=120, blank=True)
    title = models.CharField("职务", max_length=120, blank=True)
    email = models.EmailField("电子邮箱", blank=True)
    phone = models.CharField("联系电话", max_length=80, blank=True)
    notes = models.TextField("备注", blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "长期赛事人员"
        ordering = ["name", "organization", "pk"]

    def __str__(self):
        return self.name


class CompetitionRole(models.Model):
    class Category(models.TextChoices):
        COMPETITOR = "competitor", "选手"
        OFFICIAL = "official", "赛事官员"
        EXPERT = "expert", "专家或裁判"
        COACH = "coach", "教练"
        STAFF = "staff", "工作人员"
        OTHER = "other", "其他"

    code = models.CharField("角色代码", max_length=50, unique=True)
    name = models.CharField("角色名称", max_length=120)
    category = models.CharField("角色类别", max_length=20, choices=Category.choices)
    description = models.TextField("说明", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = verbose_name_plural = "赛事角色"
        ordering = ["order", "code", "pk"]

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
    started_at = models.DateTimeField("实际启动时间", null=True, blank=True)
    completed_at = models.DateTimeField("实际完成时间", null=True, blank=True)
    results_published_at = models.DateTimeField("成绩发布时间", null=True, blank=True)
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
        permissions = [
            ("view_all_assessment", "查看全部竞赛与考核"),
            ("change_all_assessment", "维护全部竞赛与考核"),
        ]

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
    scheduled_start_at = models.DateTimeField("计划开始时间", null=True, blank=True)
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

    @property
    def scheduled_end_at(self):
        if self.scheduled_start_at is None or self.duration_minutes is None:
            return None
        return self.scheduled_start_at + timedelta(minutes=self.duration_minutes)


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
    competition_person = models.ForeignKey(
        CompetitionPerson,
        verbose_name="长期赛事人员",
        on_delete=models.SET_NULL,
        related_name="assessment_participations",
        null=True,
        blank=True,
    )
    external_code = models.CharField("外部代码", max_length=100, blank=True)
    display_name = models.CharField("显示名称", max_length=150)
    role = models.ForeignKey(
        CompetitionRole,
        verbose_name="赛事角色",
        on_delete=models.PROTECT,
        related_name="participants",
    )
    organization = models.CharField("单位", max_length=200, blank=True)
    country_or_region = models.CharField("国家或地区", max_length=120, blank=True)
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
            models.UniqueConstraint(
                fields=["assessment", "competition_person"],
                condition=Q(competition_person__isnull=False),
                name="uniq_assessmentparticipant_competition_person",
            ),
            models.CheckConstraint(
                condition=Q(user__isnull=True) | Q(competition_person__isnull=True),
                name="assessmentparticipant_single_linked_source",
            ),
            models.CheckConstraint(
                condition=~Q(display_name=""),
                name="assessmentparticipant_display_name_required",
            ),
        ]

    def populate_snapshot_fields(self):
        if self.user_id and self.competition_person_id:
            return
        if self.competition_person_id:
            if not self.display_name:
                self.display_name = self.competition_person.name
            if not self.organization:
                self.organization = self.competition_person.organization
            if not self.country_or_region:
                self.country_or_region = self.competition_person.country_or_region
        elif self.user_id and not self.display_name:
            self.display_name = get_user_display_name(self.user)
        elif self.external_code and not self.display_name:
            self.display_name = self.external_code

    def clean(self):
        super().clean()
        self.populate_snapshot_fields()
        if self.user_id and self.competition_person_id:
            raise ValidationError("参与人员不能同时关联系统用户和长期赛事人员。")
        if not self.display_name:
            raise ValidationError({"display_name": "参与人员必须有显示名称。"})

    def save(self, *args, **kwargs):
        self.populate_snapshot_fields()
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class AssessmentFinalResult(models.Model):
    participant = models.OneToOneField(
        AssessmentParticipant,
        verbose_name="选手",
        on_delete=models.CASCADE,
        related_name="final_result",
    )
    rank = models.PositiveIntegerField("名次", null=True, blank=True)
    is_official = models.BooleanField("官方结果", default=False)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="确认人",
        on_delete=models.SET_NULL,
        related_name="confirmed_assessment_final_results",
        null=True,
        blank=True,
    )
    confirmed_at = models.DateTimeField("确认时间", null=True, blank=True)
    notes = models.TextField("备注", blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)
    awards = models.ManyToManyField(
        "AssessmentAward",
        through="AssessmentResultAward",
        related_name="final_results",
        blank=True,
    )

    class Meta:
        verbose_name = verbose_name_plural = "评测最终结果"
        ordering = ["participant__assessment", "rank", "participant__display_name", "pk"]

    def clean(self):
        super().clean()
        if self.participant_id and self.participant.role.category != CompetitionRole.Category.COMPETITOR:
            raise ValidationError({"participant": "只有选手类参与人员可以拥有最终结果。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def assessment(self):
        return self.participant.assessment

    def __str__(self):
        return f"{self.participant} / {self.rank or '-'}"


class AssessmentFinalScore(models.Model):
    class ScoreType(models.TextChoices):
        RAW = "raw", "原始成绩"
        PERCENTAGE = "percentage", "百分制成绩"
        WORLDSKILLS = "worldskills", "WorldSkills 标准化成绩"
        CUSTOM = "custom", "自定义成绩"

    final_result = models.ForeignKey(
        AssessmentFinalResult,
        verbose_name="最终结果",
        on_delete=models.CASCADE,
        related_name="scores",
    )
    score_type = models.CharField("成绩类型", max_length=20, choices=ScoreType.choices)
    label = models.CharField("成绩名称", max_length=120)
    value = models.DecimalField("成绩值", max_digits=12, decimal_places=4)
    max_value = models.DecimalField("参考最大值", max_digits=12, decimal_places=4, null=True, blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    metadata = models.JSONField("元数据", default=dict, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "评测最终成绩"
        ordering = ["final_result", "order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["final_result", "score_type", "label"],
                name="uniq_assessment_final_score_type_label",
            )
        ]

    def __str__(self):
        return f"{self.label}: {self.value}"


class AssessmentAward(models.Model):
    class Category(models.TextChoices):
        GOLD = "gold", "金牌"
        SILVER = "silver", "银牌"
        BRONZE = "bronze", "铜牌"
        EXCELLENCE = "excellence", "优胜奖"
        OTHER = "other", "其他"

    assessment = models.ForeignKey(
        Assessment,
        verbose_name="竞赛与考核",
        on_delete=models.CASCADE,
        related_name="awards",
    )
    code = models.CharField("奖项代码", max_length=50)
    name = models.CharField("奖项名称", max_length=120)
    category = models.CharField("奖项类别", max_length=20, choices=Category.choices, default=Category.OTHER)
    description = models.TextField("说明", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    metadata = models.JSONField("元数据", default=dict, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "评测奖项"
        ordering = ["assessment", "order", "name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "code"], name="uniq_assessment_award_code"),
        ]

    def __str__(self):
        return self.name


class AssessmentResultAward(models.Model):
    final_result = models.ForeignKey(
        AssessmentFinalResult,
        verbose_name="最终结果",
        on_delete=models.CASCADE,
        related_name="award_links",
    )
    award = models.ForeignKey(
        AssessmentAward,
        verbose_name="奖项",
        on_delete=models.PROTECT,
        related_name="result_links",
    )
    notes = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "最终结果奖项"
        constraints = [
            models.UniqueConstraint(fields=["final_result", "award"], name="uniq_assessment_result_award"),
        ]

    def clean(self):
        super().clean()
        if (
            self.final_result_id
            and self.award_id
            and self.final_result.participant.assessment_id != self.award.assessment_id
        ):
            raise ValidationError({"award": "奖项必须属于最终结果对应的竞赛或考核。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.final_result} / {self.award}"


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
