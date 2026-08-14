from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TrainingCycle(models.Model):
    class Status(models.TextChoices):
        PLANNING = "planning", "筹备中"
        ACTIVE = "active", "进行中"
        COMPLETED = "completed", "已结束"
        ARCHIVED = "archived", "已归档"

    skill_project = models.ForeignKey(
        "standards.SkillProject",
        verbose_name="技能项目",
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
        verbose_name = "训练周期"
        verbose_name_plural = "训练周期"
        ordering = ["-start_date", "name"]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "结束日期不能早于开始日期。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


class TrainingLog(models.Model):
    training_cycle = models.ForeignKey(
        TrainingCycle,
        verbose_name="训练周期",
        on_delete=models.PROTECT,
        related_name="training_logs",
    )
    capability_domain = models.ForeignKey(
        "standards.CapabilityDomain",
        verbose_name="能力领域",
        on_delete=models.SET_NULL,
        related_name="training_logs",
        null=True,
        blank=True,
    )
    training_date = models.DateField("训练日期", default=timezone.localdate)
    topic = models.CharField("训练主题", max_length=150)
    summary = models.TextField("训练摘要", blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传者",
        on_delete=models.PROTECT,
        related_name="training_logs",
    )
    archive_assets = GenericRelation(
        "archives.ArchiveAsset",
        content_type_field="target_content_type",
        object_id_field="target_object_id",
        related_query_name="training_log",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "训练日志"
        verbose_name_plural = "训练日志"
        ordering = ["-training_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["training_cycle", "uploaded_by", "training_date"],
                name="uniq_traininglog_cycle_user_date",
            ),
        ]
        permissions = [
            ("view_all_traininglog", "查看全部训练日志"),
            ("change_all_traininglog", "修改全部训练日志"),
            ("view_traininglog_statistics", "查看训练日志统计"),
            ("export_traininglog_archive", "导出训练日志归档"),
        ]

    def clean(self):
        super().clean()
        if self.training_cycle_id and self.capability_domain_id:
            if self.training_cycle.skill_project_id != self.capability_domain.skill_project_id:
                raise ValidationError({"capability_domain": "能力领域必须属于训练周期对应的技能项目。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def primary_asset(self):
        return self.archive_assets.order_by("-uploaded_at", "-pk").first()

    def __str__(self):
        return f"{self.training_date:%Y-%m-%d} / {self.uploaded_by} / {self.topic}"

# Create your models here.
