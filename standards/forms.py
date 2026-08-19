from __future__ import annotations

from django import forms
from django.urls import reverse

from core.utils.forms import StyledFormMixin

from .models import (
    Skill,
    SkillProject,
    SkillTreeNode,
    SkillTreeVersion,
    SkillWSOSMap,
    TechnicalDomain,
    TechnicalDomainMembership,
    WSOSSection,
    WSOSVersion,
)
from .selectors import is_project_admin, manageable_domains_for
from .services import find_skill_term_conflicts, normalize_skill_term, split_skill_terms


class DefaultSkillProjectFormMixin:
    """为新建表单提供显式默认技能项目，不覆盖业务上下文或用户输入。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, "instance", None)
        if self.is_bound or getattr(instance, "pk", None) or "skill_project" in self.initial:
            return
        default_project = SkillProject.objects.filter(is_default=True, is_active=True).first()
        if default_project:
            self.initial["skill_project"] = default_project


class SkillProjectForm(StyledFormMixin, forms.ModelForm):
    def _get_validation_exclusions(self):
        exclusions = super()._get_validation_exclusions()
        exclusions.add("is_default")
        return exclusions

    class Meta:
        model = SkillProject
        fields = ["code", "name", "short_name", "description", "order", "is_active", "is_default"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class TechnicalDomainForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TechnicalDomain
        fields = ["skill_project", "code", "name", "description", "order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class TechnicalDomainMembershipForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TechnicalDomainMembership
        fields = ["technical_domain", "user", "role"]


class SkillForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    tags_text = forms.CharField(label="标签", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    aliases_text = forms.CharField(label="别名", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    confirm_distinct = forms.BooleanField(label="我已确认这不是同一技能", required=False)
    preserve_old_name = forms.BooleanField(label="将原名称保留为别名", required=False, initial=True)

    class Meta:
        model = Skill
        fields = [
            "skill_project",
            "primary_domain",
            "related_domains",
            "name",
            "description",
            "difficulty",
            "is_core",
            "is_assessable",
            "order",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "related_domains": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        self.old_name = getattr(kwargs.get("instance"), "name", "")
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["tags_text"].initial = "\n".join(self.instance.tags or [])
            self.fields["aliases_text"].initial = "\n".join(self.instance.aliases)
            self.fields.pop("confirm_distinct")
        else:
            self.fields.pop("preserve_old_name")

        allowed_domains = TechnicalDomain.objects.all()
        if user is not None:
            allowed_domains = manageable_domains_for(user)
            if self.instance.pk:
                allowed_domains = (
                    allowed_domains
                    | self.instance.related_domains.all()
                    | TechnicalDomain.objects.filter(pk=self.instance.primary_domain_id)
                ).distinct()
        selectable_domains = allowed_domains if self.instance.pk else allowed_domains.filter(is_active=True)
        self.fields["primary_domain"].queryset = selectable_domains
        self.fields["related_domains"].queryset = selectable_domains

        allowed_projects = SkillProject.objects.filter(
            pk__in=allowed_domains.values("skill_project_id"),
            is_active=True,
        ).distinct()
        if user is not None and is_project_admin(user):
            allowed_projects = SkillProject.objects.filter(is_active=True)
        if self.instance.pk:
            allowed_projects = (
                allowed_projects | SkillProject.objects.filter(pk=self.instance.skill_project_id)
            ).distinct()
        self.fields["skill_project"].queryset = allowed_projects
        self.fields["skill_project"].widget.attrs.update(
            {
                "hx-get": reverse("standards:skill_domain_fields"),
                "hx-target": "#skill-primary-domain-field",
                "hx-trigger": "change",
                "hx-swap": "outerHTML",
            }
        )
        self.fields["name"].widget.attrs.update(
            {
                "hx-get": reverse("standards:skill_candidates"),
                "hx-target": "#skill-candidates",
                "hx-trigger": "input changed delay:350ms, search",
                "hx-include": "#id_skill_project",
            }
        )

        project = self.initial.get("skill_project") or getattr(self.instance, "skill_project", None)
        if self.is_bound and self.data.get("skill_project"):
            project = SkillProject.objects.filter(pk=self.data.get("skill_project")).first()
        if not self.is_bound and not self.instance.pk:
            project_id = getattr(project, "pk", project)
            if not project_id or not allowed_projects.filter(pk=project_id).exists():
                project = allowed_projects.filter(is_default=True).first() or allowed_projects.first()
                if project:
                    self.initial["skill_project"] = project
        if project:
            self.fields["primary_domain"].queryset = self.fields["primary_domain"].queryset.filter(
                skill_project=project
            )
            self.fields["related_domains"].queryset = self.fields["related_domains"].queryset.filter(
                skill_project=project
            )
        else:
            self.fields["primary_domain"].queryset = TechnicalDomain.objects.none()
            self.fields["related_domains"].queryset = TechnicalDomain.objects.none()

    @staticmethod
    def _split_text(value):
        return split_skill_terms(value)

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get("skill_project")
        primary = cleaned.get("primary_domain")
        related = cleaned.get("related_domains")
        name = cleaned.get("name", "")
        aliases = self._split_text(cleaned.get("aliases_text", ""))
        if project and primary and primary.skill_project_id != project.pk:
            self.add_error("primary_domain", "主要技术领域必须属于当前技能项目。")
        for domain in related or []:
            if project and domain.skill_project_id != project.pk:
                self.add_error("related_domains", "关联技术领域必须属于当前技能项目。")
                break
            if primary and domain.pk == primary.pk:
                self.add_error("related_domains", "主要技术领域不能重复加入关联技术领域。")
                break
        if project and name:
            conflicts = find_skill_term_conflicts(
                skill_project=project,
                terms=[name, *aliases],
                exclude_skill=self.instance if self.instance.pk else None,
            )
            name_key = normalize_skill_term(name)
            for conflict in conflicts:
                if conflict.normalized_term == name_key:
                    self.add_error("name", f"该称谓已属于技能 {conflict.skill}。")
                else:
                    self.add_error("aliases_text", f"称谓“{conflict.term}”已属于技能 {conflict.skill}。")
        return cleaned

    def save(self, commit=True):
        self.instance.tags = self._split_text(self.cleaned_data.get("tags_text"))
        return super().save(commit=commit)


class SkillTreeVersionForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SkillTreeVersion
        fields = ["skill_project", "version", "name", "description", "is_current"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class SkillTreeNodeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SkillTreeNode
        fields = [
            "tree_version",
            "technical_domain",
            "parent",
            "node_type",
            "code",
            "name",
            "description",
            "skill",
            "order",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        version = self.initial.get("tree_version") or getattr(self.instance, "tree_version", None)
        if self.is_bound and self.data.get("tree_version"):
            version = (
                SkillTreeVersion.objects.filter(pk=self.data.get("tree_version"))
                .select_related("skill_project")
                .first()
            )
        if version:
            self.fields["technical_domain"].queryset = TechnicalDomain.objects.filter(
                skill_project=version.skill_project
            )
            self.fields["skill"].queryset = Skill.objects.filter(skill_project=version.skill_project, is_active=True)
            self.fields["parent"].queryset = SkillTreeNode.objects.filter(tree_version=version).exclude(
                pk=self.instance.pk
            )


class WSOSVersionForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WSOSVersion
        fields = ["skill_project", "code", "name", "description", "is_current"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class WSOSSectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WSOSSection
        fields = ["wsos_version", "code", "name", "description", "weight", "order"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class SkillWSOSMapForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SkillWSOSMap
        fields = ["skill", "wsos_section", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}
