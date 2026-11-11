from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from core.models import TimestampedModel

from core.uploads import (
    PrivateMediaStorage,
    TRAINING_ATTACHMENT_UPLOAD_SPEC,
    TRAINING_LOG_UPLOAD_SPEC,
    UploadSignatureValidator,
)
from .log_files import TrainingLogStorage


training_storage = PrivateMediaStorage("training")


def log_template_upload_path(instance, filename):
    return str(Path("log-templates", str(instance.training_cycle_id), Path(filename).name))


class TrainingLogTemplate(TimestampedModel):
    name = models.CharField("模板名称", max_length=150)
    training_cycle = models.ForeignKey("TrainingCycle", verbose_name="训练周期", on_delete=models.PROTECT,
                                       related_name="log_templates")
    file = models.FileField("模板文件", storage=training_storage, upload_to=log_template_upload_path,
                            max_length=500, validators=[*TRAINING_LOG_UPLOAD_SPEC.validators(),
                                                        UploadSignatureValidator()])
    description = models.TextField("说明", blank=True)
    order = models.PositiveIntegerField("显示顺序", default=0)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练日志模板"
        ordering = ["order", "name", "pk"]

    def __str__(self):
        return self.name


def training_upload_path(instance, filename):
    if hasattr(instance, "change_id"):
        return str(Path("changes", str(instance.change_id), Path(filename).name))
    if hasattr(instance, "progress"):
        return str(Path("progress", str(instance.progress_id), Path(filename).name))
    if hasattr(instance, "training_task"):
        task = instance.training_task
        return str(Path("tasks", task.training_plan.training_cycle.code, str(task.pk or "new"), Path(filename).name))
    if hasattr(instance, "task_execution"):
        execution = instance.task_execution
        return str(
            Path(
                "executions",
                execution.training_task.training_plan.training_cycle.code,
                str(execution.pk or "new"),
                Path(filename).name,
            )
        )
    if isinstance(instance, TrainingPlan):
        return str(Path("plans", instance.training_cycle.code, Path(filename).name))
    return str(Path("logs", instance.training_cycle.code, f"{instance.training_date:%Y/%m}", Path(filename).name))


class TrainingCycle(models.Model):
    class Status(models.TextChoices):
        PLANNING = "planning", "筹备中"
        ACTIVE = "active", "进行中"
        COMPLETED = "completed", "已完成"
        ARCHIVED = "archived", "已归档"

    skill_project = models.ForeignKey(
        "standards.SkillProject", verbose_name="技能项目", on_delete=models.PROTECT, related_name="training_cycles"
    )
    parent = models.ForeignKey(
        "self", verbose_name="父周期", on_delete=models.PROTECT, related_name="stages", null=True, blank=True
    )
    skill_tree_versions = models.ManyToManyField(
        "standards.SkillTreeVersion",
        verbose_name="各技术领域技能树版本",
        through="TrainingCycleSkillTreeVersion",
        related_name="training_cycles",
    )
    code = models.CharField("周期代码", max_length=50, unique=True)
    name = models.CharField("周期名称", max_length=120)
    start_date = models.DateField("开始日期")
    end_date = models.DateField("结束日期", null=True, blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.PLANNING)
    description = models.TextField("描述", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练周期"
        ordering = ["-start_date", "name"]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "结束日期不能早于开始日期。"})
        if self.status != self.Status.PLANNING and (
            not self.pk or not self.skill_tree_version_links.exists()
        ):
            raise ValidationError({"status": "训练周期进入进行中前必须至少固定一个技术领域的技能树版本。"})
        if self.pk:
            previous_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            allowed_transitions = {
                self.Status.PLANNING: {self.Status.PLANNING, self.Status.ACTIVE},
                self.Status.ACTIVE: {self.Status.ACTIVE, self.Status.COMPLETED},
                self.Status.COMPLETED: {self.Status.COMPLETED, self.Status.ARCHIVED},
                self.Status.ARCHIVED: {self.Status.ARCHIVED},
            }
            if previous_status and self.status not in allowed_transitions[previous_status]:
                raise ValidationError({"status": "训练周期状态只能按筹备中、进行中、已完成、已归档依次推进。"})
            if self.skill_tree_version_links.exclude(technical_domain__skill_project_id=self.skill_project_id).exists():
                raise ValidationError({"skill_project": "已有领域快照不属于所选技能项目，请先调整快照。"})
            if self.stages.exclude(skill_project_id=self.skill_project_id).exists():
                raise ValidationError({"skill_project": "已有阶段周期不属于所选技能项目，不能修改。"})
        if self.parent_id:
            if self.pk and self.parent_id == self.pk:
                raise ValidationError({"parent": "父周期不能是自身。"})
            if self.parent.parent_id:
                raise ValidationError({"parent": "训练周期第一版最多支持总周期与阶段周期两层。"})
            if self.pk and self.stages.exists():
                raise ValidationError({"parent": "已有阶段周期的总周期不能设置父周期。"})
            if self.parent.skill_project_id != self.skill_project_id:
                raise ValidationError({"parent": "父周期必须属于同一技能项目。"})
            if self.pk and self.skill_tree_version_links.exclude(
                technical_domain_id__in=self.parent.skill_tree_version_links.values("technical_domain_id")
            ).exists():
                raise ValidationError({"parent": "已有领域快照不属于所选父周期，请先调整快照。"})
            if self.start_date < self.parent.start_date or (
                self.parent.end_date and (not self.end_date or self.end_date > self.parent.end_date)
            ):
                raise ValidationError("阶段周期日期必须位于父周期范围内。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def can_add_skill_tree_bindings(self):
        return self.status == self.Status.ACTIVE or not self.skill_tree_bindings_locked

    @property
    def skill_tree_bindings_locked(self):
        if self.status != self.Status.PLANNING:
            return True
        return self.plans.filter(tasks__executions__started_at__isnull=False).exists()


class TrainingCycleSkillTreeVersion(models.Model):
    training_cycle = models.ForeignKey(
        TrainingCycle,
        verbose_name="训练周期",
        on_delete=models.CASCADE,
        related_name="skill_tree_version_links",
    )
    technical_domain = models.ForeignKey(
        "standards.TechnicalDomain",
        verbose_name="技术领域",
        on_delete=models.PROTECT,
        related_name="training_cycle_version_links",
    )
    skill_tree_version = models.ForeignKey(
        "standards.SkillTreeVersion",
        verbose_name="技能树版本",
        on_delete=models.PROTECT,
        related_name="training_cycle_links",
    )

    class Meta:
        verbose_name = "训练周期领域技能树版本"
        verbose_name_plural = "训练周期领域技能树版本"
        ordering = ["training_cycle", "technical_domain__order", "technical_domain_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["training_cycle", "technical_domain"],
                name="uniq_trainingcycle_domain_tree",
            ),
            models.UniqueConstraint(
                fields=["training_cycle", "skill_tree_version"],
                name="uniq_trainingcycle_tree_version",
            ),
        ]

    def clean(self):
        super().clean()
        if self.training_cycle_id and not self.pk:
            cycle = TrainingCycle.objects.get(pk=self.training_cycle_id)
            if not cycle.can_add_skill_tree_bindings:
                raise ValidationError("训练周期的技能树版本快照已经锁定，不能再新增。")
        if self.training_cycle_id and self.technical_domain_id:
            if self.training_cycle.skill_project_id != self.technical_domain.skill_project_id:
                raise ValidationError({"technical_domain": "技术领域必须属于训练周期对应的技能项目。"})
            if self.training_cycle.parent_id and not self.training_cycle.parent.skill_tree_version_links.filter(
                technical_domain_id=self.technical_domain_id
            ).exists():
                raise ValidationError({"technical_domain": "阶段周期只能使用父周期已经包含的技术领域。"})
        if self.skill_tree_version_id and self.technical_domain_id:
            if self.skill_tree_version.technical_domain_id != self.technical_domain_id:
                raise ValidationError({"skill_tree_version": "技能树版本必须属于所选技术领域。"})
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "training_cycle_id",
                "technical_domain_id",
                "skill_tree_version_id",
            ).first()
            binding_changed = previous and any(
                previous[field] != getattr(self, field)
                for field in (
                    "training_cycle_id",
                    "technical_domain_id",
                    "skill_tree_version_id",
                )
            )
            if binding_changed:
                if previous["training_cycle_id"] != self.training_cycle_id and not TrainingCycle.objects.get(pk=self.training_cycle_id).can_add_skill_tree_bindings:
                    raise ValidationError("目标训练周期的技能树版本快照已经锁定，不能再新增。")
                cycle = TrainingCycle.objects.get(pk=previous["training_cycle_id"])
                if cycle.skill_tree_bindings_locked:
                    raise ValidationError("训练周期的技能树版本快照已经锁定，不能再修改。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def removal_error(self):
        cycle = TrainingCycle.objects.get(pk=self.training_cycle_id)
        if cycle.skill_tree_bindings_locked:
            return "训练周期的技能树版本快照已经锁定，不能再修改。"
        schedule_uses_domain = TrainingScheduleSlot.objects.filter(day__training_plan__training_cycle=cycle).filter(
            Q(domains__pk=self.technical_domain_id) | Q(primary_domain_id=self.technical_domain_id)
        ).exists()
        if cycle.plans.filter(tasks__domain_links__technical_domain_id=self.technical_domain_id).exists() or schedule_uses_domain:
            return "该技术领域已被排班或训练任务使用，不能从周期中移除。"
        if type(self).objects.filter(
            training_cycle__parent=cycle,
            technical_domain_id=self.technical_domain_id,
        ).exists():
            return "该技术领域已被阶段周期使用，不能从父周期中移除。"
        return ""

    def delete(self, *args, **kwargs):
        if error := self.removal_error():
            raise ValidationError(error)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.training_cycle} / {self.technical_domain} / {self.skill_tree_version}"


class TrainingCycleMember(models.Model):
    class Role(models.TextChoices):
        COMPETITOR = "competitor", "选手"
        COACH = "coach", "教练"

    training_cycle = models.ForeignKey(
        TrainingCycle, verbose_name="训练周期", on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="training_cycle_memberships",
    )
    role = models.CharField("角色", max_length=20, choices=Role.choices)
    is_current = models.BooleanField("当前周期", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练周期成员"
        constraints = [
            models.UniqueConstraint(fields=["training_cycle", "user"], name="uniq_trainingcycle_member"),
            models.UniqueConstraint(fields=["user"], condition=Q(is_current=True), name="uniq_current_cycle_per_user"),
        ]

    def has_task_links(self):
        return (
            TaskExecution.objects.filter(
                user_id=self.user_id, training_task__training_plan__training_cycle_id=self.training_cycle_id
            ).exists()
            or TrainingTaskCoach.objects.filter(
                user_id=self.user_id, training_task__training_plan__training_cycle_id=self.training_cycle_id
            ).exists()
            or TrainingScheduleSlot.objects.filter(day__training_plan__training_cycle_id=self.training_cycle_id).filter(
                Q(coaches__pk=self.user_id)
            ).exists()
            or TrainingScheduleDay.objects.filter(training_plan__training_cycle_id=self.training_cycle_id, duty_coaches__pk=self.user_id).exists()
        )

    def removal_error(self):
        if self.has_task_links():
            return "该成员已有任务关联，不能移除。"
        if TrainingLog.objects.filter(author_id=self.user_id, training_cycle_id=self.training_cycle_id).exists():
            return "该成员已有训练日志，不能移除。"
        return ""

    def clean(self):
        super().clean()
        previous = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if previous and (previous.user_id != self.user_id or previous.training_cycle_id != self.training_cycle_id):
            raise ValidationError("成员的用户与训练周期不可修改，请移除后重新添加。")
        if previous and previous.role != self.role and previous.has_task_links():
            raise ValidationError({"role": "该成员已有任务关联，不能改变身份。"})
        if self.is_current and (not previous or not previous.is_current):
            if self.training_cycle.status != TrainingCycle.Status.ACTIVE:
                raise ValidationError({"is_current": "只有进行中的训练周期可以设为当前周期。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if error := self.removal_error():
            raise ValidationError(error)
        return super().delete(*args, **kwargs)


class TrainingPlan(models.Model):
    TIME_FIELDS = tuple(f"{period}_{edge}" for period in ("early", "morning", "afternoon", "evening") for edge in ("start", "end"))
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"
        COMPLETED = "completed", "已完成"
        ARCHIVED = "archived", "已归档"

    training_cycle = models.ForeignKey(
        TrainingCycle, verbose_name="训练周期", on_delete=models.PROTECT, related_name="plans"
    )
    title = models.CharField("计划标题", max_length=180)
    start_date = models.DateField("开始日期")
    end_date = models.DateField("结束日期")
    objective = models.TextField("训练目标")
    responsible_coaches = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='+', verbose_name='负责教练')
    duty_personnel = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='+', verbose_name='值班人员')
    schedulers = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="scheduled_training_plans", verbose_name="排班人员")
    approvers = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="approved_training_plans", verbose_name="审批人员")
    task_managers = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="managed_training_plans", verbose_name="任务管理员")
    schedule_published_at = models.DateTimeField("排班发布时间", null=True, blank=True)
    published_at = models.DateTimeField("计划发布时间", null=True, blank=True)
    early_start = models.TimeField("早读开始时间", null=True, blank=True)
    early_end = models.TimeField("早读结束时间", null=True, blank=True)
    morning_start = models.TimeField("上午开始时间", null=True, blank=True)
    morning_end = models.TimeField("上午结束时间", null=True, blank=True)
    afternoon_start = models.TimeField("下午开始时间", null=True, blank=True)
    afternoon_end = models.TimeField("下午结束时间", null=True, blank=True)
    evening_start = models.TimeField("晚上开始时间", null=True, blank=True)
    evening_end = models.TimeField("晚上结束时间", null=True, blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.DRAFT)
    source_file = models.FileField(
        "原始计划文件",
        storage=training_storage,
        upload_to=training_upload_path,
        validators=[*TRAINING_ATTACHMENT_UPLOAD_SPEC.validators(), UploadSignatureValidator()],
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="创建人", on_delete=models.PROTECT, related_name="created_training_plans"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练计划"
        ordering = ["-start_date", "title"]
        constraints = [models.CheckConstraint(condition=Q(**{f"{period}_start__isnull": True, f"{period}_end__isnull": True}) | Q(**{f"{period}_start__isnull": False, f"{period}_end__isnull": False, f"{period}_end__gt": models.F(f"{period}_start")}), name=f"training_plan_{period}_positive_time") for period in ("early", "morning", "afternoon", "evening")]
        permissions = [
            ("schedule_trainingplan", "可以编排训练计划"),
            ("approve_trainingplan", "可以审批训练计划调整"),
            ("manage_plan_tasks", "可以管理指定计划的任务"),
        ]

    def clean(self):
        super().clean()
        previous_end = None
        for period in ("early", "morning", "afternoon", "evening"):
            start, end = getattr(self, f"{period}_start"), getattr(self, f"{period}_end")
            if start is None and end is None:
                continue  # 历史快照不一致的计划保留空值，编辑时由表单要求补齐。
            if start is None or end is None or start >= end:
                raise ValidationError({f"{period}_end": "开始时间必须早于结束时间，且不能跨午夜。"})
            if previous_end and start < previous_end:
                raise ValidationError({f"{period}_start": "四个时段须依次排列且不能重叠。"})
            previous_end = end
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            if original.training_cycle_id != self.training_cycle_id:
                raise ValidationError("计划创建后不能修改训练周期，请另建计划。")
            fields = ("start_date", "end_date", *self.TIME_FIELDS)
            if any(getattr(original, name) != getattr(self, name) for name in fields):
                from .scheduling import check_plan_structure_edit
                check_plan_structure_edit(
                    original, self.start_date, self.end_date,
                    changed_periods={
                        name.rsplit("_", 1)[0] for name in self.TIME_FIELDS
                        if getattr(original, name) != getattr(self, name)
                    },
                )
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "结束日期不能早于开始日期。"})
        if self.training_cycle_id and self.start_date and self.end_date:
            if self.start_date < self.training_cycle.start_date or (
                self.training_cycle.end_date and self.end_date > self.training_cycle.end_date
            ):
                raise ValidationError("训练计划日期必须位于训练周期范围内。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def display_status(self):
        if self.end_date < timezone.localdate():
            return "已完成"
        return "已发布" if self.published_at else "未发布"


class TrainingPlanDutyOrder(TimestampedModel):
    training_plan = models.ForeignKey(TrainingPlan, on_delete=models.CASCADE, related_name="duty_orders")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = verbose_name_plural = "计划值班顺序"
        constraints = [models.UniqueConstraint(fields=("training_plan", "user"), name="training_plan_duty_order_unique")]


class TrainingScheduleDay(TimestampedModel):
    training_plan = models.ForeignKey(TrainingPlan, on_delete=models.CASCADE, related_name="schedule_days", verbose_name="训练计划")
    date = models.DateField("日期")
    duty_all = models.BooleanField("全体值班", default=False)
    duty_coaches = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="training_duty_days", verbose_name="值班教练")
    note = models.TextField("日备注", blank=True)
    has_been_filled = models.BooleanField("已首次填写", default=False)
    revision = models.PositiveIntegerField("版本", default=0)

    class Meta:
        verbose_name = verbose_name_plural = "每日训练安排"
        ordering = ["date", "pk"]
        constraints = [models.UniqueConstraint(fields=["training_plan", "date"], name="uniq_plan_schedule_day")]

    def clean(self):
        super().clean()
        if self.training_plan_id and self.date and not self.training_plan.start_date <= self.date <= self.training_plan.end_date:
            raise ValidationError("安排日期必须位于训练计划范围内。")


class TrainingScheduleSlot(TimestampedModel):
    class Period(models.TextChoices):
        EARLY = "early", "早读"
        MORNING = "morning", "上午"
        AFTERNOON = "afternoon", "下午"
        EVENING = "evening", "晚上"

    class Kind(models.TextChoices):
        PENDING = "pending", "待排班"
        TECHNICAL = "technical", "技术训练"
        GENERAL = "general", "其他"
        COMPREHENSIVE = "comprehensive", "综合"
        REST = "rest", "休息"
        UNUSED = "unused", "不安排"

    day = models.ForeignKey(TrainingScheduleDay, on_delete=models.CASCADE, related_name="slots", verbose_name="每日安排")
    period = models.CharField("时段", max_length=12, choices=Period.choices)
    kind = models.CharField("类型", max_length=13, choices=Kind.choices, default=Kind.PENDING)
    domains = models.ManyToManyField("standards.TechnicalDomain", blank=True, verbose_name="技术领域")
    primary_domain = models.ForeignKey("standards.TechnicalDomain", on_delete=models.PROTECT, null=True, blank=True, related_name="primary_training_slots", verbose_name="主要领域")
    coaches_all = models.BooleanField("全体负责", default=False)
    coaches = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="training_schedule_slots", verbose_name="负责教练")
    has_been_filled = models.BooleanField("已首次填写", default=False)
    revision = models.PositiveIntegerField("版本", default=0)
    starts_at = models.DateTimeField("开始时间快照", null=True, blank=True)
    ends_at = models.DateTimeField("结束时间快照", null=True, blank=True)
    is_configured = models.BooleanField("已设置时段", default=True)

    @property
    def is_locked(self):
        # 旧安排缺少可核实的时间快照时只读，不能猜测历史时间。
        return self.ends_at is None or timezone.now() >= self.ends_at

    class Meta:
        verbose_name = verbose_name_plural = "训练排班时段"
        constraints = [
            models.UniqueConstraint(fields=["day", "period"], name="uniq_training_day_period"),
            models.CheckConstraint(condition=Q(starts_at__isnull=True, ends_at__isnull=True) | Q(starts_at__isnull=False, ends_at__isnull=False, ends_at__gt=models.F("starts_at")), name="training_slot_valid_time_snapshot"),
            models.CheckConstraint(condition=Q(is_configured=True) | Q(is_configured=False, starts_at__isnull=True, ends_at__isnull=True, kind="unused"), name="training_slot_unconfigured_empty"),
        ]

    def __str__(self):
        return f"{self.day.date} · {self.get_period_display()}"


class TrainingScheduleChange(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已批准"
        REJECTED = "rejected", "已驳回"

    training_plan = models.ForeignKey(TrainingPlan, on_delete=models.PROTECT, related_name="schedule_changes", verbose_name="训练计划")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="training_schedule_requests", verbose_name="申请人")
    reason = models.TextField("调整原因")
    payload = models.JSONField("调整内容")
    status = models.CharField("状态", max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="training_schedule_reviews", verbose_name="审批人")
    reviewed_at = models.DateTimeField("审批时间", null=True, blank=True)
    review_note = models.TextField("审批意见", blank=True)
    confirmations = models.JSONField("教练依次确认记录", default=list, blank=True)
    confirmation_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="training_change_confirmations", verbose_name="涉及教练")

    class Meta:
        verbose_name = verbose_name_plural = "训练排班调整申请"
        ordering = ["-created_at", "-pk"]


class TrainingChangeAttachment(TimestampedModel):
    change = models.ForeignKey(TrainingScheduleChange, on_delete=models.PROTECT, related_name="attachments", verbose_name="调整申请")
    file = models.FileField("待审批任务附件", storage=training_storage, upload_to=training_upload_path, validators=[*TRAINING_ATTACHMENT_UPLOAD_SPEC.validators(), UploadSignatureValidator()])
    original_filename = models.CharField("原始文件名", max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="上传者")

    class Meta:
        verbose_name = verbose_name_plural = "训练调整申请附件"


class TrainingChangeRecordQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("变更记录不能覆盖。")

    def delete(self):
        raise ValidationError("变更记录不能删除。")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("变更记录不能覆盖。")


class TrainingChangeRecord(TimestampedModel):
    objects = TrainingChangeRecordQuerySet.as_manager()
    training_plan = models.ForeignKey(
        TrainingPlan, on_delete=models.PROTECT, related_name="change_records", verbose_name="训练计划",
        null=True, blank=True,
    )
    deleted_plan = models.JSONField("已删除计划快照", null=True, blank=True)
    task = models.ForeignKey("TrainingTask", on_delete=models.PROTECT, null=True, blank=True, related_name="change_records", verbose_name="训练任务")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="操作者")
    action = models.CharField("动作", max_length=80)
    reason = models.TextField("原因", blank=True)
    before = models.JSONField("修改前", default=dict)
    after = models.JSONField("修改后", default=dict)

    class Meta:
        verbose_name = verbose_name_plural = "训练计划变更记录"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(training_plan__isnull=False, deleted_plan__isnull=True)
                    | Q(training_plan__isnull=True, deleted_plan__isnull=False, task__isnull=True)
                ),
                name="training_change_record_plan_or_snapshot",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("变更记录不能覆盖。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("变更记录不能删除。")


class TrainingTask(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "低"
        NORMAL = "normal", "普通"
        HIGH = "high", "高"
        URGENT = "urgent", "紧急"

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"
        CANCELLED = "cancelled", "已取消"

    training_plan = models.ForeignKey(
        TrainingPlan, verbose_name="训练计划", on_delete=models.PROTECT, related_name="tasks"
    )
    schedule_slot = models.ForeignKey("TrainingScheduleSlot", verbose_name="排班时段", on_delete=models.PROTECT, related_name="tasks", null=True, blank=True)
    assign_all = models.BooleanField("分配计划内全体选手", default=True)
    selected_competitors = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="selected_training_tasks", verbose_name="指定选手")
    planned_date = models.DateField("计划日期")
    title = models.CharField("任务标题", max_length=180)
    description = models.TextField("任务描述", blank=True)
    requirements = models.TextField("训练要求", blank=True)
    estimated_minutes = models.PositiveIntegerField("预计用时（分钟）", null=True, blank=True)
    priority = models.CharField("优先级", max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.DRAFT)
    order = models.PositiveIntegerField("排序", default=0)
    cancelled_at = models.DateTimeField("取消时间", null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="cancelled_training_tasks", verbose_name="取消人")
    cancel_reason = models.TextField("取消原因", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="创建人", on_delete=models.PROTECT, related_name="created_training_tasks"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练任务"
        ordering = ["planned_date", "order", "pk"]

    @property
    def skill_project(self):
        return self.training_plan.training_cycle.skill_project

    @property
    def is_locked(self):
        if self.schedule_slot_id:
            return self.schedule_slot.is_locked
        return self.executions.filter(Q(started_at__isnull=False) | Q(status__in=["in_progress", "completed", "partially_completed", "blocked"])).exists()

    def clean(self):
        super().clean()
        if self.schedule_slot_id and (
            self.schedule_slot.day.training_plan_id != self.training_plan_id
            or self.schedule_slot.day.date != self.planned_date
        ):
            raise ValidationError("任务必须属于排班时段的计划和日期。")
        if (
            self.training_plan_id
            and self.planned_date
            and not (self.training_plan.start_date <= self.planned_date <= self.training_plan.end_date)
        ):
            raise ValidationError({"planned_date": "计划日期必须位于训练计划范围内。"})
        if self.pk and self.is_locked and not getattr(self, "_definition_approved", False):
            previous = type(self).objects.get(pk=self.pk)
            protected = (
                "training_plan_id",
                "planned_date",
                "title",
                "description",
                "requirements",
                "estimated_minutes",
            )
            if any(getattr(previous, field) != getattr(self, field) for field in protected):
                raise ValidationError("任务已锁定，不能修改日期、内容和核心要求。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.planned_date:%Y-%m-%d} · {self.title}"


class TrainingTaskDomain(models.Model):
    class Role(models.TextChoices):
        PRIMARY = "primary", "主要领域"
        RELATED = "related", "关联领域"

    training_task = models.ForeignKey(
        TrainingTask, verbose_name="训练任务", on_delete=models.CASCADE, related_name="domain_links"
    )
    technical_domain = models.ForeignKey(
        "standards.TechnicalDomain",
        verbose_name="技术领域",
        on_delete=models.PROTECT,
        related_name="training_task_links",
    )
    role = models.CharField("角色", max_length=20, choices=Role.choices, default=Role.RELATED)

    class Meta:
        verbose_name = verbose_name_plural = "训练任务技术领域"
        constraints = [
            models.UniqueConstraint(fields=["training_task", "technical_domain"], name="uniq_trainingtask_domain"),
            models.UniqueConstraint(
                fields=["training_task"], condition=Q(role="primary"), name="uniq_primary_domain_per_trainingtask"
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.training_task_id
            and self.technical_domain_id
            and self.training_task.skill_project.pk != self.technical_domain.skill_project_id
        ):
            raise ValidationError({"technical_domain": "技术领域必须属于训练任务对应的技能项目。"})
        if self.training_task_id and self.technical_domain_id:
            cycle = self.training_task.training_plan.training_cycle
            if not cycle.skill_tree_version_links.filter(technical_domain_id=self.technical_domain_id).exists():
                raise ValidationError({"technical_domain": "训练任务只能使用周期已固定技能树版本的技术领域。"})
        if self.training_task_id and self.training_task.is_locked and not getattr(self.training_task, "_definition_approved", False):
            raise ValidationError("已有选手开始执行后不能修改任务技术领域。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class TrainingTaskSkill(models.Model):
    class Role(models.TextChoices):
        PRIMARY = "primary", "主要技能"
        RELATED = "related", "关联技能"

    training_task = models.ForeignKey(
        TrainingTask, verbose_name="训练任务", on_delete=models.CASCADE, related_name="skill_links"
    )
    skill = models.ForeignKey(
        "standards.Skill", verbose_name="技能", on_delete=models.PROTECT, related_name="training_task_links"
    )
    role = models.CharField("角色", max_length=20, choices=Role.choices, default=Role.RELATED)
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = verbose_name_plural = "训练任务技能"
        ordering = ["training_task", "role", "order"]
        constraints = [models.UniqueConstraint(fields=["training_task", "skill"], name="uniq_trainingtask_skill")]

    def clean(self):
        super().clean()
        if self.training_task_id and self.skill_id:
            if self.training_task.skill_project.pk != self.skill.skill_project_id:
                raise ValidationError({"skill": "技能必须属于训练任务对应的技能项目。"})
            domain_ids = set(self.training_task.domain_links.values_list("technical_domain_id", flat=True))
            skill_domain_ids = {self.skill.primary_domain_id, *self.skill.related_domains.values_list("pk", flat=True)}
            if domain_ids and not domain_ids.intersection(skill_domain_ids):
                raise ValidationError({"skill": "技能与任务技术领域必须至少有一个交集。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class TrainingTaskCoach(models.Model):
    training_task = models.ForeignKey(
        TrainingTask, verbose_name="训练任务", on_delete=models.CASCADE, related_name="coach_links"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="教练",
        on_delete=models.PROTECT,
        related_name="training_task_assignments",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练任务教练"
        constraints = [
            models.UniqueConstraint(fields=["training_task", "user"], name="uniq_trainingtask_coach"),
        ]

    def clean(self):
        super().clean()
        if (
            self.training_task_id
            and self.user_id
            and not self.training_task.training_plan.training_cycle.members.filter(
                user_id=self.user_id, role=TrainingCycleMember.Role.COACH
            ).exists()
        ):
            if not self.user.is_superuser:
                raise ValidationError({"user": "任务教练必须是当前训练周期的教练成员。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class TrainingTaskAttachment(models.Model):
    training_task = models.ForeignKey(
        TrainingTask, verbose_name="训练任务", on_delete=models.CASCADE, related_name="attachments"
    )
    title = models.CharField("标题", max_length=150, blank=True)
    file = models.FileField(
        "文件",
        storage=training_storage,
        upload_to=training_upload_path,
        validators=[*TRAINING_ATTACHMENT_UPLOAD_SPEC.validators(), UploadSignatureValidator()],
    )
    original_filename = models.CharField("原始文件名", max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传者",
        on_delete=models.PROTECT,
        related_name="uploaded_training_task_attachments",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            self.original_filename = Path(self.file.name).name
        super().save(*args, **kwargs)


class TaskExecution(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "未开始"
        IN_PROGRESS = "in_progress", "进行中"
        COMPLETED = "completed", "已完成"
        PARTIALLY_COMPLETED = "partially_completed", "部分完成"
        BLOCKED = "blocked", "受阻"
        UNFINISHED = "unfinished", "未完成"
        CANCELLED = "cancelled", "已取消"

    training_task = models.ForeignKey(
        TrainingTask, verbose_name="训练任务", on_delete=models.PROTECT, related_name="executions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="选手", on_delete=models.PROTECT, related_name="task_executions"
    )
    status = models.CharField("状态", max_length=30, choices=Status.choices, default=Status.ASSIGNED)
    assigned_at = models.DateTimeField("分配时间", auto_now_add=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    completed_at = models.DateTimeField("完成时间", null=True, blank=True)
    actual_minutes = models.PositiveIntegerField(
        "实际用时（分钟）", null=True, blank=True, validators=[MinValueValidator(0)]
    )
    completion_note = models.TextField("完成情况", blank=True)
    problems = models.TextField("遇到的问题", blank=True)
    problem_resolved = models.BooleanField("问题已解决", null=True, blank=True)
    solution = models.TextField("解决方法", blank=True)
    reflection = models.TextField("个人总结", blank=True)
    coach_feedback = models.TextField("教练反馈", blank=True)
    feedback_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="反馈教练",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_execution_feedbacks",
    )
    feedback_at = models.DateTimeField("反馈时间", null=True, blank=True)
    revoked_at = models.DateTimeField("撤销时间", null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="revoked_training_assignments", verbose_name="撤销人")
    revoke_reason = models.TextField("撤销原因", blank=True)
    legacy_status = models.CharField("历史原始状态", max_length=30, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练任务执行"
        ordering = ["training_task__planned_date", "user"]
        constraints = [
            models.UniqueConstraint(fields=["training_task", "user"], name="uniq_trainingtask_execution_user")
        ]

    def clean(self):
        super().clean()
        if (
            self.training_task_id
            and self.user_id
            and not self.pk and not self.training_task.training_plan.training_cycle.members.filter(
                user_id=self.user_id, role=TrainingCycleMember.Role.COMPETITOR
            ).exists()
        ):
            raise ValidationError({"user": "训练任务只能分配给当前周期的选手成员。"})

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.status not in {self.Status.ASSIGNED, self.Status.CANCELLED} and not self.started_at:
            self.started_at = now
        if self.status in {self.Status.COMPLETED, self.Status.PARTIALLY_COMPLETED} and not self.completed_at:
            self.completed_at = now
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.training_task} / {self.user.display_name}"


class TaskExecutionAttachment(models.Model):
    task_execution = models.ForeignKey(
        TaskExecution, verbose_name="任务执行", on_delete=models.CASCADE, related_name="attachments"
    )
    title = models.CharField("标题", max_length=150, blank=True)
    file = models.FileField(
        "文件",
        storage=training_storage,
        upload_to=training_upload_path,
        validators=[*TRAINING_ATTACHMENT_UPLOAD_SPEC.validators(), UploadSignatureValidator()],
    )
    original_filename = models.CharField("原始文件名", max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传者",
        on_delete=models.PROTECT,
        related_name="uploaded_execution_attachments",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    def clean(self):
        super().clean()
        if self.task_execution_id and self.uploaded_by_id != self.task_execution.user_id:
            raise ValidationError({"uploaded_by": "选手只能向自己的任务执行记录上传附件。"})

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            self.original_filename = Path(self.file.name).name
        self.clean()
        super().save(*args, **kwargs)


class TrainingLog(TimestampedModel):
    canonical_filename = models.CharField("归档文件名", max_length=255, null=True, blank=True, editable=False)
    training_cycle = models.ForeignKey(
        TrainingCycle, verbose_name="训练周期", on_delete=models.PROTECT, related_name="training_logs"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="作者", on_delete=models.PROTECT, related_name="training_logs"
    )
    training_date = models.DateField("训练日期", default=timezone.localdate)
    topic = models.CharField("训练主题", max_length=150, blank=True)
    is_backfill = models.BooleanField("历史补交", default=False, editable=False)
    summary = models.TextField("训练摘要", blank=True)
    document = models.FileField(
        "日志文件",
        storage=TrainingLogStorage("training"),
        max_length=500,
        upload_to=training_upload_path,
        validators=[*TRAINING_LOG_UPLOAD_SPEC.validators(), UploadSignatureValidator()],
        null=True,
        blank=True,
    )
    executions = models.ManyToManyField(TaskExecution, through="TrainingLogExecution", related_name="training_logs")

    class Meta:
        verbose_name = verbose_name_plural = "训练日志"
        ordering = ["-training_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["training_cycle", "author", "training_date"], name="uniq_traininglog_cycle_author_date"
            ),
            models.UniqueConstraint(
                fields=["training_cycle", "canonical_filename"], name="uniq_traininglog_cycle_filename"
            ),
        ]
        permissions = [
            ("view_all_traininglog", "查看全部训练日志"),
            ("change_all_traininglog", "修改全部训练日志"),
            ("delete_all_traininglog", "删除全部训练日志"),
            ("view_traininglog_statistics", "查看训练日志统计"),
            ("export_traininglog_archive", "导出训练日志归档"),
        ]

    def __str__(self):
        return f"{self.training_date:%Y-%m-%d} / {self.author.display_name} / {self.topic}"

    def clean(self):
        super().clean()
        if self.training_date and self.training_date > timezone.localdate():
            raise ValidationError({"training_date": "训练日期不能晚于今天。"})


class TrainingPeriodConfig(TimestampedModel):
    period = models.CharField("时段", max_length=12, choices=TrainingScheduleSlot.Period.choices, unique=True)
    start_time = models.TimeField("开始时间")
    end_time = models.TimeField("结束时间")

    class Meta:
        verbose_name = verbose_name_plural = "训练时段时间配置"
        constraints = [models.CheckConstraint(condition=Q(end_time__gt=models.F("start_time")), name="training_period_positive_duration")]

    def __str__(self):
        return self.get_period_display()


class TrainingPlanParticipant(TimestampedModel):
    training_plan = models.ForeignKey(TrainingPlan, on_delete=models.PROTECT, related_name="participants", verbose_name="训练计划")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="training_plan_participations", verbose_name="选手")
    is_active = models.BooleanField("参与中", default=True)
    was_initial = models.BooleanField("计划创建时选手", default=False)

    class Meta:
        verbose_name = verbose_name_plural = "计划参与选手"
        constraints = [models.UniqueConstraint(fields=["training_plan", "user"], name="uniq_training_plan_participant")]


class TrainingPlanStaff(TimestampedModel):
    class Role(models.TextChoices):
        COACH = "coach", "负责教练"
        DUTY = "duty", "值班人员"

    training_plan = models.ForeignKey(TrainingPlan, on_delete=models.PROTECT, related_name="staff_members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="training_plan_staff")
    role = models.CharField("职责", max_length=10, choices=Role.choices)
    is_active = models.BooleanField("参与中", default=True)

    class Meta:
        verbose_name = verbose_name_plural = "计划工作人员"
        constraints = [
            models.UniqueConstraint(fields=["training_plan", "user", "role"], name="uniq_training_plan_staff_role"),
        ]


class TrainingAssignmentCoach(TimestampedModel):
    """保存曾负责某项分配的教练，交接后仍可确定自主任务指导范围。"""
    execution = models.ForeignKey(TaskExecution, on_delete=models.PROTECT, related_name="responsible_coach_history", verbose_name="任务分配")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="training_assignment_history", verbose_name="教练")

    class Meta:
        verbose_name = verbose_name_plural = "任务分配负责教练历史"
        constraints = [models.UniqueConstraint(fields=["execution", "user"], name="uniq_training_assignment_coach")]


class PersonalTrainingTask(TimestampedModel):
    training_plan = models.ForeignKey(TrainingPlan, on_delete=models.PROTECT, related_name="personal_tasks", verbose_name="训练计划")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="personal_training_tasks", verbose_name="选手")
    date = models.DateField("训练日期")
    period = models.CharField("时段", max_length=12, choices=TrainingScheduleSlot.Period.choices, blank=True)
    domain = models.ForeignKey("standards.TechnicalDomain", on_delete=models.PROTECT, null=True, blank=True, verbose_name="训练领域")
    skills = models.ManyToManyField("standards.Skill", blank=True, verbose_name="关联技能")
    title = models.CharField("任务标题", max_length=180)
    description = models.TextField("任务说明（Markdown）", blank=True)
    status = models.CharField("执行状态", max_length=30, default="assigned", choices=[("assigned", "未开始"), ("in_progress", "进行中"), ("completed", "已完成"), ("unfinished", "未完成")])
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="deleted_personal_training_tasks", verbose_name="删除人")

    class Meta:
        verbose_name = verbose_name_plural = "自主训练任务"
        ordering = ["date", "created_at", "pk"]

    def clean(self):
        super().clean()
        if self.training_plan_id and self.date and not self.training_plan.start_date <= self.date <= self.training_plan.end_date:
            raise ValidationError({"date": "自主任务日期必须位于计划周期内。"})
        if self.domain_id and self.domain.skill_project_id != self.training_plan.training_cycle.skill_project_id:
            raise ValidationError({"domain": "领域必须属于计划的技能项目。"})

    def __str__(self):
        return self.title


def process_target_constraint(name):
    return models.CheckConstraint(
        condition=(Q(execution__isnull=False, personal_task__isnull=True) | Q(execution__isnull=True, personal_task__isnull=False)), name=name
    )


class ImmutableTrainingRecord(TimestampedModel):
    objects = TrainingChangeRecordQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("训练历史记录不能覆盖。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("训练历史记录不能删除。")


class TrainingStateChange(ImmutableTrainingRecord):
    execution = models.ForeignKey(TaskExecution, on_delete=models.PROTECT, null=True, blank=True, related_name="state_changes", verbose_name="官方任务分配")
    personal_task = models.ForeignKey(PersonalTrainingTask, on_delete=models.PROTECT, null=True, blank=True, related_name="state_changes", verbose_name="自主任务")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="操作人")
    before = models.CharField("原状态", max_length=30)
    after = models.CharField("新状态", max_length=30)

    @property
    def before_label(self):
        return dict(TaskExecution.Status.choices).get(self.before, self.before)

    @property
    def after_label(self):
        return dict(TaskExecution.Status.choices).get(self.after, self.after)

    class Meta:
        verbose_name = verbose_name_plural = "训练执行状态历史"
        ordering = ["created_at", "pk"]
        constraints = [process_target_constraint("training_state_one_target")]


class TrainingProgress(TimestampedModel):
    execution = models.ForeignKey(TaskExecution, on_delete=models.PROTECT, null=True, blank=True, related_name="progress_records", verbose_name="官方任务分配")
    personal_task = models.ForeignKey(PersonalTrainingTask, on_delete=models.PROTECT, null=True, blank=True, related_name="progress_records", verbose_name="自主任务")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="选手")
    completed = models.TextField("已完成的部分／已掌握知识（Markdown）", blank=True)
    problems = models.TextField("未完成的部分／存在问题（Markdown）", blank=True)
    is_legacy = models.BooleanField("历史汇总导入", default=False)

    class Meta:
        verbose_name = verbose_name_plural = "训练进度"
        ordering = ["created_at", "pk"]
        constraints = [process_target_constraint("training_progress_one_target")]


class TrainingProgressRevision(ImmutableTrainingRecord):
    progress = models.ForeignKey(TrainingProgress, on_delete=models.PROTECT, related_name="revisions", verbose_name="进度记录")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="修订人")
    completed = models.TextField("原已完成内容", blank=True)
    problems = models.TextField("原问题内容", blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练进度修订历史"
        ordering = ["created_at", "pk"]


class TrainingCoachFeedback(ImmutableTrainingRecord):
    execution = models.ForeignKey(TaskExecution, on_delete=models.PROTECT, null=True, blank=True, related_name="feedback_records", verbose_name="官方任务分配")
    personal_task = models.ForeignKey(PersonalTrainingTask, on_delete=models.PROTECT, null=True, blank=True, related_name="feedback_records", verbose_name="自主任务")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="教练")
    content = models.TextField("指导反馈")
    recorded_at = models.DateTimeField("反馈发生时间", default=timezone.now)
    is_legacy = models.BooleanField("历史反馈导入", default=False)

    class Meta:
        verbose_name = verbose_name_plural = "训练教练反馈"
        ordering = ["recorded_at", "pk"]
        constraints = [process_target_constraint("training_feedback_one_target")]


class TrainingProgressAttachment(TimestampedModel):
    progress = models.ForeignKey(TrainingProgress, on_delete=models.PROTECT, related_name="attachments", verbose_name="进度记录")
    file = models.FileField("附件", storage=training_storage, upload_to=training_upload_path, validators=[*TRAINING_ATTACHMENT_UPLOAD_SPEC.validators(), UploadSignatureValidator()])
    original_filename = models.CharField("原始文件名", max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="上传者")

    class Meta:
        verbose_name = verbose_name_plural = "训练进度附件"


class TrainingLogExecution(models.Model):
    training_log = models.ForeignKey(
        TrainingLog, verbose_name="训练日志", on_delete=models.CASCADE, related_name="execution_links"
    )
    task_execution = models.ForeignKey(
        TaskExecution, verbose_name="任务执行", on_delete=models.PROTECT, related_name="log_links"
    )
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = verbose_name_plural = "训练日志执行关联"
        ordering = ["training_log", "order"]
        constraints = [
            models.UniqueConstraint(fields=["training_log", "task_execution"], name="uniq_traininglog_execution")
        ]

    def clean(self):
        super().clean()
        if not self.training_log_id or not self.task_execution_id:
            return
        execution = self.task_execution
        log = self.training_log
        if execution.user_id != log.author_id:
            raise ValidationError({"task_execution": "训练日志只能关联作者本人的任务执行。"})
        if execution.training_task.training_plan.training_cycle_id != log.training_cycle_id:
            raise ValidationError({"task_execution": "任务执行必须属于训练日志对应周期。"})
        planned = execution.training_task.planned_date
        started = timezone.localtime(execution.started_at).date() if execution.started_at else None
        completed = timezone.localtime(execution.completed_at).date() if execution.completed_at else None
        in_actual_range = started and started <= log.training_date <= (completed or timezone.localdate())
        if planned != log.training_date and not in_actual_range:
            raise ValidationError({"task_execution": "任务计划日期或实际执行日期必须与训练日志日期合理对应。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class TrainingBoardPlan(TimestampedModel):
    training_plan = models.OneToOneField(
        TrainingPlan, on_delete=models.CASCADE, related_name="screen_listing", verbose_name="训练计划",
        help_text="免登录训练大屏公开计划名称、当天排班、教练姓名、已发布任务标题和选手任务执行的匿名汇总。",
    )

    class Meta:
        verbose_name = verbose_name_plural = "训练大屏展示计划"

    def __str__(self):
        return self.training_plan.title
