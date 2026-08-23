from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q


class SkillProject(models.Model):
    """长期稳定的技能项目本体。"""

    code = models.CharField("技能项目代码", max_length=50, unique=True)
    name = models.CharField("技能项目名称", max_length=150)
    short_name = models.CharField("简称", max_length=80, blank=True)
    description = models.TextField("描述", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    is_default = models.BooleanField(
        "默认项目",
        default=False,
        help_text="新建业务对象时优先选择此技能项目；全系统最多只能设置一个默认项目。",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "技能项目"
        verbose_name_plural = "技能项目"
        ordering = ["order", "code", "name"]
        permissions = [("manage_all_technical_domains", "管理全部训练主线技术领域")]
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=Q(is_default=True),
                name="uniq_default_skill_project",
            ),
            models.CheckConstraint(
                condition=Q(is_default=False) | Q(is_active=True),
                name="default_skill_project_must_be_active",
            ),
        ]

    def clean(self):
        super().clean()
        if self.is_default and not self.is_active:
            raise ValidationError({"is_default": "默认技能项目必须处于启用状态。"})

    def save(self, *args, **kwargs):
        self.clean()
        update_fields = kwargs.get("update_fields")
        should_switch_default = self.is_default and (
            not self.pk or update_fields is None or "is_default" in update_fields
        )
        with transaction.atomic():
            if should_switch_default:
                list(type(self).objects.select_for_update().order_by("pk").values_list("pk", flat=True))
                type(self).objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class TechnicalDomain(models.Model):
    skill_project = models.ForeignKey(
        SkillProject, verbose_name="技能项目", on_delete=models.CASCADE, related_name="technical_domains"
    )
    code = models.CharField("领域代码", max_length=50)
    name = models.CharField("领域名称", max_length=120)
    description = models.TextField("描述", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "技术领域"
        verbose_name_plural = "技术领域"
        ordering = ["skill_project", "order", "code", "name"]
        constraints = [
            models.UniqueConstraint(fields=["skill_project", "code"], name="uniq_technicaldomain_project_code")
        ]

    def __str__(self):
        return f"{self.skill_project.code} / {self.code} - {self.name}"


class TechnicalDomainMembership(models.Model):
    class Role(models.TextChoices):
        LEAD_COACH = "lead_coach", "主教练"
        COACH = "coach", "教练"

    technical_domain = models.ForeignKey(
        TechnicalDomain, verbose_name="技术领域", on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="technical_domain_memberships",
    )
    role = models.CharField("职责", max_length=20, choices=Role.choices, default=Role.COACH)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "技术领域教练"
        verbose_name_plural = "技术领域教练"
        ordering = ["technical_domain", "role", "user"]
        constraints = [
            models.UniqueConstraint(fields=["technical_domain", "user"], name="uniq_technicaldomain_membership_user")
        ]

    def __str__(self):
        return f"{self.technical_domain} / {self.user}"


class Skill(models.Model):
    skill_project = models.ForeignKey(
        SkillProject, verbose_name="技能项目", on_delete=models.CASCADE, related_name="skills"
    )
    primary_domain = models.ForeignKey(
        TechnicalDomain, verbose_name="主要技术领域", on_delete=models.PROTECT, related_name="primary_skills"
    )
    related_domains = models.ManyToManyField(
        TechnicalDomain, verbose_name="关联技术领域", related_name="related_skills", blank=True
    )
    name = models.CharField("技能名称", max_length=200)
    description = models.TextField("描述", blank=True)
    difficulty = models.PositiveSmallIntegerField(
        "难度", default=3, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    is_core = models.BooleanField("核心技能", default=False)
    is_assessable = models.BooleanField("可考核", default=True)
    tags = models.JSONField("标签", default=list, blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "技能"
        verbose_name_plural = "技能"
        ordering = ["skill_project", "primary_domain__order", "order", "name", "pk"]

    def clean(self):
        super().clean()
        if self.primary_domain_id and self.skill_project_id:
            if self.primary_domain.skill_project_id != self.skill_project_id:
                raise ValidationError({"primary_domain": "主要技术领域必须属于当前技能项目。"})
            if self.is_active and not self.primary_domain.is_active:
                raise ValidationError({"primary_domain": "启用的技能不能使用已停用的技术领域。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def aliases(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("terms")
        if prefetched is not None:
            return [term.term for term in prefetched if term.kind == SkillTerm.Kind.ALIAS]
        return list(self.terms.filter(kind=SkillTerm.Kind.ALIAS).values_list("term", flat=True))

    def __str__(self):
        return self.name


class SkillTerm(models.Model):
    """项目内唯一的技能正式名称或别名登记词条。"""

    class Kind(models.TextChoices):
        NAME = "name", "正式名称"
        ALIAS = "alias", "别名"

    skill_project = models.ForeignKey(
        SkillProject,
        verbose_name="技能项目",
        on_delete=models.CASCADE,
        related_name="skill_terms",
    )
    skill = models.ForeignKey(Skill, verbose_name="技能", on_delete=models.CASCADE, related_name="terms")
    term = models.CharField("称谓", max_length=200)
    normalized_term = models.CharField("规范化称谓", max_length=400, editable=False)
    kind = models.CharField("称谓类型", max_length=10, choices=Kind.choices)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "技能称谓"
        verbose_name_plural = "技能称谓"
        ordering = ["skill_project", "skill", "kind", "term"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(normalized_term=""),
                name="skillterm_normalized_not_empty",
            ),
            models.UniqueConstraint(
                fields=["skill_project", "normalized_term"],
                name="uniq_skillterm_project_normalized",
            ),
            models.UniqueConstraint(
                fields=["skill"],
                condition=Q(kind="name"),
                name="uniq_primary_skillterm_per_skill",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.normalized_term:
            raise ValidationError({"term": "技能称谓不能为空。"})
        if self.skill_id and self.skill_project_id and self.skill.skill_project_id != self.skill_project_id:
            raise ValidationError({"skill_project": "技能称谓必须与技能属于同一技能项目。"})

    def save(self, *args, **kwargs):
        from .services import normalize_skill_term

        self.normalized_term = normalize_skill_term(self.term)
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.term


class SkillTreeVersion(models.Model):
    technical_domain = models.ForeignKey(
        TechnicalDomain,
        verbose_name="技术领域",
        on_delete=models.PROTECT,
        related_name="skill_tree_versions",
    )
    based_on = models.ForeignKey(
        "self",
        verbose_name="基于版本",
        on_delete=models.SET_NULL,
        related_name="derived_versions",
        null=True,
        blank=True,
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
        ordering = ["technical_domain", "-is_current", "-created_at", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["technical_domain", "version"],
                name="uniq_skilltreeversion_domain_version",
            ),
            models.UniqueConstraint(
                fields=["technical_domain"],
                condition=Q(is_current=True),
                name="uniq_current_skilltreeversion_per_domain",
            ),
        ]

    @property
    def skill_project(self):
        return self.technical_domain.skill_project

    @property
    def skill_project_id(self):
        return self.technical_domain.skill_project_id

    def clean(self):
        super().clean()
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "technical_domain_id", "based_on_id"
            ).first()
            if previous and previous["technical_domain_id"] != self.technical_domain_id:
                raise ValidationError({"technical_domain": "技能树版本创建后不能更改所属技术领域。"})
            if previous and previous["based_on_id"] != self.based_on_id:
                raise ValidationError({"based_on": "技能树版本创建后不能更改基于版本。"})
        if not self.based_on_id:
            return
        if self.pk and self.based_on_id == self.pk:
            raise ValidationError({"based_on": "基于版本不能是当前版本自身。"})
        if self.technical_domain_id and self.based_on.technical_domain_id != self.technical_domain_id:
            raise ValidationError({"based_on": "基于版本必须属于同一技术领域。"})
        ancestor = self.based_on
        seen = set()
        while ancestor is not None:
            if ancestor.pk in seen or (self.pk and ancestor.pk == self.pk):
                raise ValidationError({"based_on": "基于版本不能形成循环。"})
            seen.add(ancestor.pk)
            ancestor = ancestor.based_on

    def save(self, *args, **kwargs):
        self.clean()
        with transaction.atomic():
            if self.is_current and self.technical_domain_id:
                list(
                    type(self)
                    .objects.select_for_update()
                    .filter(technical_domain_id=self.technical_domain_id)
                    .values_list("pk", flat=True)
                )
                type(self).objects.filter(technical_domain_id=self.technical_domain_id, is_current=True).exclude(
                    pk=self.pk
                ).update(is_current=False)
            super().save(*args, **kwargs)

    def __str__(self):
        suffix = "（当前）" if self.is_current else ""
        return f"{self.technical_domain} / {self.name} {self.version}{suffix}"


class SkillTreeNode(models.Model):
    tree_version = models.ForeignKey(
        SkillTreeVersion, verbose_name="技能树版本", on_delete=models.CASCADE, related_name="nodes"
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="父技能",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    skill = models.ForeignKey(
        Skill,
        verbose_name="技能",
        on_delete=models.PROTECT,
        related_name="tree_nodes",
    )
    order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "技能树节点"
        verbose_name_plural = "技能树节点"
        ordering = ["tree_version", "order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["tree_version", "skill"],
                name="uniq_skilltreenode_version_skill",
            ),
        ]

    @property
    def skill_project(self):
        return self.tree_version.skill_project

    @property
    def technical_domain(self):
        return self.tree_version.technical_domain

    @property
    def technical_domain_id(self):
        return self.tree_version.technical_domain_id

    def clean(self):
        super().clean()
        if self.skill_id and self.tree_version_id:
            if self.skill.skill_project_id != self.tree_version.skill_project_id:
                raise ValidationError({"skill": "技能必须属于技能树对应的技能项目。"})
            allowed_domain_ids = {self.skill.primary_domain_id}
            if self.skill.pk:
                allowed_domain_ids.update(self.skill.related_domains.values_list("pk", flat=True))
            if self.tree_version.technical_domain_id not in allowed_domain_ids:
                raise ValidationError({"skill": "技能未关联技能树所属技术领域。"})

        if self.parent_id and self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "父节点不能是当前节点自身。"})
        if self.parent_id:
            if self.parent.tree_version_id != self.tree_version_id:
                raise ValidationError({"parent": "父节点必须属于同一技能树版本。"})
        ancestor = self.parent if self.parent_id else None
        seen = set()
        while ancestor is not None:
            if ancestor.pk in seen or (self.pk and ancestor.pk == self.pk):
                raise ValidationError({"parent": "父节点不能是当前节点的下级节点。"})
            seen.add(ancestor.pk)
            ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_ancestors(self, include_self=False):
        ancestors = [self] if include_self else []
        parent = self.parent
        while parent is not None:
            ancestors.append(parent)
            parent = parent.parent
        ancestors.reverse()
        return ancestors

    def get_full_path(self, separator=" / "):
        return separator.join(node.skill.name for node in self.get_ancestors(include_self=True))

    def get_descendants(self, include_self=False):
        descendants = [self] if include_self else []

        def append_children(node):
            children = node.children.order_by("order", "pk")
            for child in children:
                descendants.append(child)
                append_children(child)

        if self.pk:
            append_children(self)
        return descendants

    def __str__(self):
        return self.skill.name


class WSOSVersion(models.Model):
    skill_project = models.ForeignKey(
        SkillProject, verbose_name="技能项目", on_delete=models.CASCADE, related_name="wsos_versions"
    )
    code = models.CharField("版本代码", max_length=50)
    name = models.CharField("版本名称", max_length=120)
    description = models.TextField("描述", blank=True)
    is_current = models.BooleanField("当前版本", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_wsos_versions",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "WSOS 版本"
        verbose_name_plural = "WSOS 版本"
        ordering = ["skill_project", "-is_current", "code"]
        constraints = [
            models.UniqueConstraint(fields=["skill_project", "code"], name="uniq_wsosversion_project_code"),
            models.UniqueConstraint(
                fields=["skill_project"],
                condition=Q(is_current=True),
                name="uniq_current_wsosversion_per_project",
            ),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_current and self.skill_project_id:
                type(self).objects.filter(skill_project_id=self.skill_project_id, is_current=True).exclude(
                    pk=self.pk
                ).update(is_current=False)
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.skill_project.code} / {self.name}"


class WSOSSection(models.Model):
    wsos_version = models.ForeignKey(
        WSOSVersion, verbose_name="WSOS 版本", on_delete=models.CASCADE, related_name="sections"
    )
    code = models.CharField("章节代码", max_length=50)
    name = models.CharField("章节名称", max_length=160)
    description = models.TextField("描述", blank=True)
    weight = models.DecimalField(
        "权重（%）", max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        verbose_name = "WSOS 章节"
        verbose_name_plural = "WSOS 章节"
        ordering = ["wsos_version", "order", "code"]
        constraints = [models.UniqueConstraint(fields=["wsos_version", "code"], name="uniq_wsossection_version_code")]

    def __str__(self):
        return f"{self.code} - {self.name}"


class SkillWSOSMap(models.Model):
    skill = models.ForeignKey(Skill, verbose_name="技能", on_delete=models.CASCADE, related_name="wsos_mappings")
    wsos_section = models.ForeignKey(
        WSOSSection, verbose_name="WSOS 章节", on_delete=models.PROTECT, related_name="skill_mappings"
    )
    note = models.TextField("说明", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "技能与 WSOS 映射"
        verbose_name_plural = "技能与 WSOS 映射"
        ordering = ["skill", "wsos_section__order"]
        constraints = [models.UniqueConstraint(fields=["skill", "wsos_section"], name="uniq_skill_wsos_section")]

    def clean(self):
        super().clean()
        if self.skill_id and self.wsos_section_id:
            if self.skill.skill_project_id != self.wsos_section.wsos_version.skill_project_id:
                raise ValidationError({"wsos_section": "技能与 WSOS 章节必须属于同一技能项目。"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.skill} -> {self.wsos_section}"
