from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class CompetitionSeries(models.Model):
    code = models.CharField("赛事系列代码", max_length=50, unique=True)
    name = models.CharField("赛事系列名称", max_length=120)
    description = models.TextField("描述", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "赛事系列"
        verbose_name_plural = "赛事系列"
        ordering = ["order", "code", "name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class CompetitionLevel(models.Model):
    code = models.CharField("赛事级别代码", max_length=50, unique=True)
    name = models.CharField("赛事级别名称", max_length=120)
    weight = models.DecimalField(
        "统计权重",
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "赛事级别"
        verbose_name_plural = "赛事级别"
        ordering = ["order", "code", "name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Event(models.Model):
    class EventType(models.TextChoices):
        COMPETITION = "competition", "正式竞赛"
        ASSESSMENT = "assessment", "训练考核"
        MOCK_EXAM = "mock_exam", "模拟赛"
        TRAINING_TEST = "training_test", "训练测试"
        OTHER = "other", "其他事件"

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"
        ACTIVE = "active", "进行中"
        COMPLETED = "completed", "已完成"
        ARCHIVED = "archived", "已归档"
        CANCELLED = "cancelled", "已取消"

    skill_project = models.ForeignKey(
        "standards.SkillProject",
        verbose_name="技能项目",
        on_delete=models.PROTECT,
        related_name="events",
    )
    series = models.ForeignKey(
        CompetitionSeries,
        verbose_name="赛事系列",
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
    )
    level = models.ForeignKey(
        CompetitionLevel,
        verbose_name="赛事级别",
        on_delete=models.PROTECT,
        related_name="events",
        null=True,
        blank=True,
    )
    training_cycle = models.ForeignKey(
        "training.TrainingCycle",
        verbose_name="训练周期",
        on_delete=models.SET_NULL,
        related_name="events",
        null=True,
        blank=True,
    )
    event_type = models.CharField("事件类型", max_length=30, choices=EventType.choices)
    name = models.CharField("事件名称", max_length=150)
    code = models.CharField("事件代码", max_length=50, unique=True)
    start_date = models.DateField("开始日期")
    end_date = models.DateField("结束日期", null=True, blank=True)
    location = models.CharField("地点", max_length=150, blank=True)
    description = models.TextField("描述", blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_events",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "事件"
        verbose_name_plural = "事件"
        ordering = ["-start_date", "name"]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
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
        return f"{self.name} ({self.code})"


class EventModule(models.Model):
    event = models.ForeignKey(Event, verbose_name="事件", on_delete=models.CASCADE, related_name="modules")
    code = models.CharField("模块代码", max_length=50)
    name = models.CharField("模块名称", max_length=150)
    description = models.TextField("描述", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    total_mark = models.DecimalField(
        "总分",
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    duration_minutes = models.PositiveIntegerField("时长（分钟）", default=0)
    counts_towards_ranking = models.BooleanField("计入排名分", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "事件模块"
        verbose_name_plural = "事件模块"
        ordering = ["event", "order", "code", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["event", "code"], name="uniq_eventmodule_event_code"),
        ]

    @property
    def skill_project(self):
        return self.event.skill_project

    def __str__(self):
        return f"{self.event.code} / {self.code} - {self.name}"


class EventModuleCapabilityDomainMap(models.Model):
    event_module = models.ForeignKey(
        EventModule,
        verbose_name="事件模块",
        on_delete=models.CASCADE,
        related_name="domain_mappings",
    )
    capability_domain = models.ForeignKey(
        "standards.CapabilityDomain",
        verbose_name="能力领域",
        on_delete=models.PROTECT,
        related_name="event_module_mappings",
    )
    is_primary = models.BooleanField("主领域", default=False)
    weight = models.DecimalField(
        "权重",
        max_digits=6,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    note = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = "事件模块能力领域映射"
        verbose_name_plural = "事件模块能力领域映射"
        ordering = ["event_module", "-is_primary", "capability_domain__order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["event_module", "capability_domain"],
                name="uniq_eventmodule_domain",
            ),
            models.UniqueConstraint(
                fields=["event_module"],
                condition=Q(is_primary=True),
                name="uniq_primary_domain_per_eventmodule",
            ),
        ]

    def clean(self):
        super().clean()
        if self.event_module_id and self.capability_domain_id:
            if self.event_module.event.skill_project_id != self.capability_domain.skill_project_id:
                raise ValidationError({"capability_domain": "能力领域必须属于事件模块对应的技能项目。"})
        if self.is_primary and self.event_module_id:
            qs = type(self).objects.filter(event_module_id=self.event_module_id, is_primary=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"is_primary": "同一事件模块只能设置一个主能力领域。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.event_module} -> {self.capability_domain}"


class EventParticipant(models.Model):
    class Role(models.TextChoices):
        COMPETITOR = "competitor", "选手"
        EXPERT = "expert", "专家"
        COACH = "coach", "教练"
        STAFF = "staff", "工作人员"
        OBSERVER = "observer", "观察员"
        OTHER = "other", "其他"

    event = models.ForeignKey(Event, verbose_name="事件", on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="关联用户",
        on_delete=models.PROTECT,
        related_name="event_participations",
        null=True,
        blank=True,
    )
    external_code = models.CharField("外部编号", max_length=100, blank=True)
    display_name = models.CharField("显示名称", max_length=150)
    role = models.CharField("角色", max_length=30, choices=Role.choices, default=Role.COMPETITOR)
    organization = models.CharField("所属单位", max_length=150, blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "事件参与人员"
        verbose_name_plural = "事件参与人员"
        ordering = ["event", "role", "display_name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "user"],
                condition=Q(user__isnull=False),
                name="uniq_eventparticipant_event_user",
            ),
            models.UniqueConstraint(
                fields=["event", "external_code"],
                condition=~Q(external_code=""),
                name="uniq_eventparticipant_event_external_code",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.user_id and not self.external_code and not self.display_name:
            raise ValidationError("参与人员至少需要显示名称、关联用户或外部编号。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class EventResultSummary(models.Model):
    event = models.ForeignKey(Event, verbose_name="事件", on_delete=models.CASCADE, related_name="result_summaries")
    participant = models.OneToOneField(
        EventParticipant,
        verbose_name="参与人员",
        on_delete=models.CASCADE,
        related_name="result_summary",
    )
    total_score = models.DecimalField(
        "总分",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    rank = models.PositiveIntegerField("排名", null=True, blank=True)
    award = models.CharField("奖项", max_length=100, blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "事件结果汇总"
        verbose_name_plural = "事件结果汇总"
        ordering = ["event", "rank", "-total_score", "pk"]

    def clean(self):
        super().clean()
        if self.event_id and self.participant_id and self.participant.event_id != self.event_id:
            raise ValidationError({"participant": "结果参与人员必须属于当前事件。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.event} / {self.participant}"

# Create your models here.
