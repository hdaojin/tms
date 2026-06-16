from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class SkillTree(models.Model):
    module = models.ForeignKey(
        "competition_standards.StandardModule",
        verbose_name="标准模块",
        on_delete=models.PROTECT,
        related_name="skill_trees",
    )
    name = models.CharField("技能树名称", max_length=100)
    version = models.CharField("版本", max_length=50, default="v1")
    description = models.TextField("说明", blank=True)
    is_current = models.BooleanField("当前启用", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_skill_trees",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "技能树"
        verbose_name_plural = "技能树"
        ordering = ["module__project__name", "module__code", "-is_current", "version", "name"]
        constraints = [
            models.UniqueConstraint(fields=["module", "version"], name="uniq_skilltree_module_version"),
            models.UniqueConstraint(
                fields=["module"],
                condition=models.Q(is_current=True),
                name="uniq_current_skilltree_per_module",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.is_current and self.module_id:
            type(self).objects.filter(module_id=self.module_id, is_current=True).exclude(pk=self.pk).update(
                is_current=False
            )
        super().save(*args, **kwargs)

    def __str__(self):
        suffix = "（当前）" if self.is_current else ""
        return f"{self.module.code} - {self.module.name} / {self.name} {self.version}{suffix}"


class SkillNode(models.Model):
    class NodeType(models.TextChoices):
        CATEGORY = "category", "分类"
        TOPIC = "topic", "专题"
        SKILL = "skill", "技能点"
        TASK = "task", "训练任务"

    tree = models.ForeignKey(
        SkillTree,
        verbose_name="技能树",
        on_delete=models.CASCADE,
        related_name="nodes",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="父节点",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    code = models.CharField("节点代码", max_length=100)
    name = models.CharField("节点名称", max_length=200)
    node_type = models.CharField("节点类型", max_length=20, choices=NodeType.choices, default=NodeType.SKILL)
    description = models.TextField("说明", blank=True)
    difficulty = models.PositiveSmallIntegerField(
        "默认难度",
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 最简单，5 最难。",
    )
    sort_order = models.PositiveIntegerField("显示顺序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "技能树节点"
        verbose_name_plural = "技能树节点"
        ordering = ["tree", "parent_id", "sort_order", "code", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tree", "code"], name="uniq_skillnode_tree_code"),
        ]

    def clean(self):
        super().clean()
        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError({"parent": "父节点不能是当前节点自身。"})
        if self.parent_id and self.parent.tree_id != self.tree_id:
            raise ValidationError({"parent": "父节点必须属于同一棵技能树。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def module(self):
        return self.tree.module

    def __str__(self):
        return f"{self.code} - {self.name}"
