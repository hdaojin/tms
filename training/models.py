from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.uploads import (
    PrivateMediaStorage,
    TRAINING_ATTACHMENT_UPLOAD_SPEC,
    TRAINING_LOG_UPLOAD_SPEC,
    UploadSignatureValidator,
)


training_storage = PrivateMediaStorage("training")


def training_upload_path(instance, filename):
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
    return str(Path("logs", instance.training_cycle.code, str(instance.author_id or "unknown"), Path(filename).name))


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
    skill_tree_version = models.ForeignKey(
        "standards.SkillTreeVersion",
        verbose_name="技能树版本",
        on_delete=models.PROTECT,
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
        if (
            self.skill_tree_version_id
            and self.skill_project_id
            and self.skill_tree_version.skill_project_id != self.skill_project_id
        ):
            raise ValidationError({"skill_tree_version": "技能树版本必须属于当前技能项目。"})
        if self.parent_id:
            if self.pk and self.parent_id == self.pk:
                raise ValidationError({"parent": "父周期不能是自身。"})
            if self.parent.parent_id:
                raise ValidationError({"parent": "训练周期第一版最多支持总周期与阶段周期两层。"})
            if self.parent.skill_project_id != self.skill_project_id:
                raise ValidationError({"parent": "父周期必须属于同一技能项目。"})
            if self.start_date < self.parent.start_date or (
                self.parent.end_date and (not self.end_date or self.end_date > self.parent.end_date)
            ):
                raise ValidationError("阶段周期日期必须位于父周期范围内。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


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
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练周期成员"
        constraints = [models.UniqueConstraint(fields=["training_cycle", "user"], name="uniq_trainingcycle_member")]


class TrainingPlan(models.Model):
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

    def clean(self):
        super().clean()
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "结束日期不能早于开始日期。"})
        if self.training_cycle_id and self.start_date:
            if self.start_date < self.training_cycle.start_date or (
                self.training_cycle.end_date and self.end_date > self.training_cycle.end_date
            ):
                raise ValidationError("训练计划日期必须位于训练周期范围内。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


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
    planned_date = models.DateField("计划日期")
    title = models.CharField("任务标题", max_length=180)
    description = models.TextField("任务描述", blank=True)
    requirements = models.TextField("训练要求")
    estimated_minutes = models.PositiveIntegerField("预计用时（分钟）", null=True, blank=True)
    priority = models.CharField("优先级", max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.DRAFT)
    order = models.PositiveIntegerField("排序", default=0)
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
        return self.executions.exclude(status=TaskExecution.Status.ASSIGNED).exists()

    def clean(self):
        super().clean()
        if (
            self.training_plan_id
            and self.planned_date
            and not (self.training_plan.start_date <= self.planned_date <= self.training_plan.end_date)
        ):
            raise ValidationError({"planned_date": "计划日期必须位于训练计划范围内。"})
        if self.pk and self.is_locked:
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
                raise ValidationError("已有选手开始执行后，不能修改任务日期、内容和核心要求；请取消旧任务并新建任务。")

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
        if self.training_task_id and self.training_task.is_locked:
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
        if self.training_task_id and self.training_task.is_locked:
            raise ValidationError("已有选手开始执行后不能修改任务技能。")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class TrainingTaskCoach(models.Model):
    class Role(models.TextChoices):
        PRIMARY = "primary", "主教练"
        COLLABORATOR = "collaborator", "协作教练"

    training_task = models.ForeignKey(
        TrainingTask, verbose_name="训练任务", on_delete=models.CASCADE, related_name="coach_links"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="教练",
        on_delete=models.PROTECT,
        related_name="training_task_assignments",
    )
    role = models.CharField("角色", max_length=20, choices=Role.choices, default=Role.COLLABORATOR)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练任务教练"
        constraints = [
            models.UniqueConstraint(fields=["training_task", "user"], name="uniq_trainingtask_coach"),
            models.UniqueConstraint(
                fields=["training_task"], condition=Q(role="primary"), name="uniq_primary_coach_per_trainingtask"
            ),
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
            from standards.selectors import is_project_admin

            if not is_project_admin(self.user):
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
        ASSIGNED = "assigned", "已分配"
        IN_PROGRESS = "in_progress", "进行中"
        COMPLETED = "completed", "已完成"
        PARTIALLY_COMPLETED = "partially_completed", "部分完成"
        BLOCKED = "blocked", "受阻"
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
            and not self.training_task.training_plan.training_cycle.members.filter(
                user_id=self.user_id, role=TrainingCycleMember.Role.COMPETITOR
            ).exists()
        ):
            raise ValidationError({"user": "训练任务只能分配给当前周期的选手成员。"})

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.status != self.Status.ASSIGNED and not self.started_at:
            self.started_at = now
        if self.status in {self.Status.COMPLETED, self.Status.PARTIALLY_COMPLETED} and not self.completed_at:
            self.completed_at = now
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.training_task} / {self.user}"


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


class TrainingLog(models.Model):
    training_cycle = models.ForeignKey(
        TrainingCycle, verbose_name="训练周期", on_delete=models.PROTECT, related_name="training_logs"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="作者", on_delete=models.PROTECT, related_name="training_logs"
    )
    training_date = models.DateField("训练日期", default=timezone.localdate)
    topic = models.CharField("训练主题", max_length=150)
    summary = models.TextField("训练摘要", blank=True)
    document = models.FileField(
        "正式训练日志",
        storage=training_storage,
        upload_to=training_upload_path,
        validators=[*TRAINING_LOG_UPLOAD_SPEC.validators(), UploadSignatureValidator()],
        null=True,
        blank=True,
    )
    executions = models.ManyToManyField(TaskExecution, through="TrainingLogExecution", related_name="training_logs")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "训练日志"
        ordering = ["-training_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["training_cycle", "author", "training_date"], name="uniq_traininglog_cycle_author_date"
            )
        ]
        permissions = [
            ("view_all_traininglog", "查看全部训练日志"),
            ("change_all_traininglog", "修改全部训练日志"),
            ("view_traininglog_statistics", "查看训练日志统计"),
            ("export_traininglog_archive", "导出训练日志归档"),
        ]

    def __str__(self):
        return f"{self.training_date:%Y-%m-%d} / {self.author} / {self.topic}"


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
