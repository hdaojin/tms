from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class SkillProject(models.Model):
    """长期稳定的技能项目本体。"""

    code = models.CharField("技能项目代码", max_length=50, unique=True)
    name = models.CharField("技能项目名称", max_length=150)
    short_name = models.CharField("简称", max_length=80, blank=True)
    description = models.TextField("描述", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "技能项目"
        verbose_name_plural = "技能项目"
        ordering = ["order", "code", "name"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class CapabilityDomain(models.Model):
    """长期能力领域，不等同于某届比赛的 A/B/C/D 模块。"""

    skill_project = models.ForeignKey(
        SkillProject,
        verbose_name="技能项目",
        on_delete=models.CASCADE,
        related_name="capability_domains",
    )
    code = models.CharField("领域代码", max_length=50)
    name = models.CharField("领域名称", max_length=120)
    description = models.TextField("描述", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "能力领域"
        verbose_name_plural = "能力领域"
        ordering = ["skill_project", "order", "code", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["skill_project", "code"],
                name="uniq_capabilitydomain_project_code",
            ),
        ]

    def __str__(self):
        return f"{self.skill_project.code} / {self.code} - {self.name}"


class SkillTreeVersion(models.Model):
    """覆盖整个技能项目的标准技能树版本。"""

    skill_project = models.ForeignKey(
        SkillProject,
        verbose_name="技能项目",
        on_delete=models.CASCADE,
        related_name="skill_tree_versions",
    )
    version = models.CharField("版本", max_length=50)
    name = models.CharField("版本名称", max_length=120)
    description = models.TextField("描述", blank=True)
    is_current = models.BooleanField("当前版本", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_skill_tree_versions",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "标准技能树版本"
        verbose_name_plural = "标准技能树版本"
        ordering = ["skill_project", "-is_current", "-created_at", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["skill_project", "version"],
                name="uniq_skilltreeversion_project_version",
            ),
            models.UniqueConstraint(
                fields=["skill_project"],
                condition=Q(is_current=True),
                name="uniq_current_skilltreeversion_per_project",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.is_current and self.skill_project_id:
            type(self).objects.filter(
                skill_project_id=self.skill_project_id,
                is_current=True,
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def __str__(self):
        suffix = "（当前）" if self.is_current else ""
        return f"{self.skill_project.code} / {self.name} {self.version}{suffix}"


class SkillNode(models.Model):
    class NodeType(models.TextChoices):
        CATEGORY = "CATEGORY", "技能分类"
        TOPIC = "TOPIC", "能力主题"
        SKILL = "SKILL", "标准技能点"

    tree_version = models.ForeignKey(
        SkillTreeVersion,
        verbose_name="技能树版本",
        on_delete=models.CASCADE,
        related_name="nodes",
    )
    capability_domain = models.ForeignKey(
        CapabilityDomain,
        verbose_name="能力领域",
        on_delete=models.PROTECT,
        related_name="skill_nodes",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="父节点",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    node_type = models.CharField("节点类型", max_length=20, choices=NodeType.choices)
    code = models.CharField("节点代码", max_length=100)
    name = models.CharField("节点名称", max_length=200)
    description = models.TextField("描述", blank=True)
    difficulty = models.PositiveSmallIntegerField(
        "难度",
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    is_core = models.BooleanField("核心技能", default=False)
    is_assessable = models.BooleanField("可考核", default=True)
    tags = models.JSONField("标签", default=list, blank=True)
    aliases = models.JSONField("别名", default=list, blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "技能节点"
        verbose_name_plural = "技能节点"
        ordering = ["tree_version", "capability_domain__order", "parent_id", "order", "code", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tree_version", "code"],
                name="uniq_skillnode_treeversion_code",
            ),
        ]

    @property
    def skill_project(self):
        return self.tree_version.skill_project

    def clean(self):
        super().clean()
        if self.capability_domain_id and self.tree_version_id:
            if self.capability_domain.skill_project_id != self.tree_version.skill_project_id:
                raise ValidationError({"capability_domain": "能力领域必须属于当前技能树版本对应的技能项目。"})
        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "父节点不能是当前节点自身。"})
        if self.parent_id:
            if self.parent.tree_version_id != self.tree_version_id:
                raise ValidationError({"parent": "父节点必须属于同一技能树版本。"})
            if self.parent.capability_domain_id != self.capability_domain_id:
                raise ValidationError({"parent": "父节点必须属于同一能力领域。"})

        parent = self.parent if self.parent_id else None
        while parent is not None:
            if self.pk and parent.pk == self.pk:
                raise ValidationError({"parent": "父节点不能是当前节点的下级节点。"})
            parent = parent.parent

        if self.parent_id is None and self.node_type != self.NodeType.CATEGORY:
            raise ValidationError({"node_type": "根节点只能是技能分类。"})
        if self.parent_id:
            parent_type = self.parent.node_type
            if parent_type == self.NodeType.CATEGORY and self.node_type not in {self.NodeType.TOPIC, self.NodeType.SKILL}:
                raise ValidationError({"node_type": "技能分类下只能创建能力主题或标准技能点。"})
            if parent_type == self.NodeType.TOPIC and self.node_type != self.NodeType.SKILL:
                raise ValidationError({"node_type": "能力主题下只能创建标准技能点。"})
            if parent_type == self.NodeType.SKILL:
                raise ValidationError({"parent": "标准技能点下不能再创建子节点。"})
        if self.pk and self.node_type == self.NodeType.SKILL and self.children.exists():
            raise ValidationError({"node_type": "已有子节点的节点不能改为标准技能点。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def is_skill(self):
        return self.node_type == self.NodeType.SKILL

    def get_ancestors(self, include_self=False):
        ancestors = [self] if include_self else []
        parent = self.parent
        while parent is not None:
            ancestors.append(parent)
            parent = parent.parent
        ancestors.reverse()
        return ancestors

    def get_full_path(self, separator=" / "):
        return separator.join(f"{node.code} {node.name}" for node in self.get_ancestors(include_self=True))

    def get_descendants(self, include_self=False, active_only=False):
        descendants = [self] if include_self else []

        def append_children(node):
            children = node.children.order_by("order", "code", "name", "pk")
            if active_only:
                children = children.filter(is_active=True)
            for child in children:
                descendants.append(child)
                append_children(child)

        if self.pk:
            append_children(self)
        return descendants

    def __str__(self):
        return f"{self.code} - {self.name}"

# Create your models here.
