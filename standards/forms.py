from __future__ import annotations

from django import forms
from django.core.exceptions import PermissionDenied
from django.db import models
from django.urls import reverse

from core.utils.forms import ImmutableCodeFormMixin, StyledFormMixin

from .models import (
    Skill,
    SkillProject,
    SkillTreeNode,
    SkillTreeVersion,
    SkillWSOSMap,
    TechnicalDomain,
    WSOSSection,
    WSOSVersion,
)
from .selectors import can_manage_domain, scoped_domains_for
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


class SkillProjectForm(ImmutableCodeFormMixin, StyledFormMixin, forms.ModelForm):
    def _get_validation_exclusions(self):
        exclusions = super()._get_validation_exclusions()
        exclusions.add("is_default")
        return exclusions

    class Meta:
        model = SkillProject
        fields = ["code", "name", "short_name", "description", "order", "is_active", "is_default"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "code": forms.TextInput(attrs={"maxlength": 12, "pattern": "[A-Za-z0-9]{1,12}"}),
        }


class TechnicalDomainForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TechnicalDomain
        fields = ["skill_project", "code", "name", "description", "order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


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
        labels = {"order": "排序"}
        help_texts = {"order": "仅影响技能的普通排序，不影响技能树中的位置和顺序。"}

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

        permission = "standards.change_skill" if self.instance.pk else "standards.add_skill"
        primary_domains = TechnicalDomain.objects.all()
        related_domains = TechnicalDomain.objects.all()
        if user is not None:
            primary_domains = scoped_domains_for(user, permission)
            related_domains = primary_domains
            if self.instance.pk:
                primary_domains = (
                    primary_domains | TechnicalDomain.objects.filter(pk=self.instance.primary_domain_id)
                ).distinct()
                related_domains = (
                    related_domains
                    | self.instance.related_domains.all()
                    | TechnicalDomain.objects.filter(pk=self.instance.primary_domain_id)
                ).distinct()
        selectable_primary_domains = primary_domains if self.instance.pk else primary_domains.filter(is_active=True)
        selectable_related_domains = related_domains if self.instance.pk else related_domains.filter(is_active=True)
        self.fields["primary_domain"].queryset = selectable_primary_domains
        self.fields["related_domains"].queryset = selectable_related_domains

        allowed_projects = SkillProject.objects.filter(
            pk__in=primary_domains.values("skill_project_id"),
            is_active=True,
        ).distinct()
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
        if (
            self.user is not None
            and primary
            and not can_manage_domain(
                self.user,
                primary,
                "standards.change_skill" if self.instance.pk else "standards.add_skill",
            )
        ):
            self.add_error("primary_domain", "你没有在该技术领域维护技能的权限。")
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


class SkillTreeVersionForm(StyledFormMixin, forms.ModelForm):
    class CreationMode(models.TextChoices):
        CURRENT = "current", "基于当前版本创建"
        EXISTING = "existing", "基于已有版本创建"
        BLANK = "blank", "创建空白版本"

    creation_mode = forms.ChoiceField(
        label="创建方式",
        choices=CreationMode.choices,
        widget=forms.RadioSelect,
        required=False,
    )
    source_version = forms.ModelChoiceField(
        label="基于版本",
        queryset=SkillTreeVersion.objects.none(),
        required=False,
    )

    class Meta:
        model = SkillTreeVersion
        fields = ["version", "name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, technical_domain=None, actor=None, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        self.technical_domain = technical_domain or getattr(self.instance, "technical_domain", None)
        if self.instance.pk:
            self.fields.pop("creation_mode")
            self.fields.pop("source_version")
            return
        versions = SkillTreeVersion.objects.filter(technical_domain=self.technical_domain).order_by(
            "-is_current", "-created_at", "-pk"
        )
        self.fields["source_version"].queryset = versions
        current = versions.filter(is_current=True).first()
        latest = versions.first()
        if current:
            self.initial.setdefault("creation_mode", self.CreationMode.CURRENT)
            self.initial.setdefault("source_version", current)
        elif latest:
            self.initial.setdefault("creation_mode", self.CreationMode.EXISTING)
            self.initial.setdefault("source_version", latest)
        else:
            self.initial.setdefault("creation_mode", self.CreationMode.BLANK)

    def clean(self):
        cleaned = super().clean()
        version = cleaned.get("version")
        if self.technical_domain and version:
            duplicate = SkillTreeVersion.objects.filter(
                technical_domain=self.technical_domain,
                version=version,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("version", "该技术领域已存在相同版本号。")
        if self.instance.pk:
            return cleaned
        mode = cleaned.get("creation_mode") or self.CreationMode.BLANK
        source = cleaned.get("source_version")
        if mode == self.CreationMode.CURRENT:
            source = SkillTreeVersion.objects.filter(
                technical_domain=self.technical_domain,
                is_current=True,
            ).first()
            if source is None:
                self.add_error("creation_mode", "当前技术领域尚无当前版本，请选择历史版本或创建空白版本。")
        elif mode == self.CreationMode.EXISTING and source is None:
            self.add_error("source_version", "请选择一个已有版本。")
        elif mode == self.CreationMode.BLANK:
            source = None
        if source is not None and source.technical_domain_id != self.technical_domain.pk:
            self.add_error("source_version", "基于版本必须属于当前技术领域。")
        cleaned["resolved_source_version"] = source
        return cleaned

    def save(self, commit=True):
        if self.actor is None or not self.actor.is_superuser:
            raise PermissionDenied
        if self.instance.pk:
            return super().save(commit=commit)
        source = self.cleaned_data.get("resolved_source_version")
        if source is not None:
            from .services import clone_skill_tree_version

            self.instance = clone_skill_tree_version(
                source_version=source,
                version=self.cleaned_data["version"],
                name=self.cleaned_data["name"],
                description=self.cleaned_data.get("description", ""),
                actor=self.actor,
            )
            return self.instance
        self.instance.technical_domain = self.technical_domain
        self.instance.created_by = self.actor
        self.instance.is_current = False
        return super().save(commit=commit)


class SkillTreeQuickAddForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label="技能名称", max_length=200)
    existing_skill_id = forms.IntegerField(required=False, widget=forms.HiddenInput())


class SkillTreeAttachExistingForm(StyledFormMixin, forms.Form):
    new_parent = forms.ModelChoiceField(
        label="挂载位置",
        queryset=SkillTreeNode.objects.none(),
        required=False,
        empty_label="作为当前技术领域的根技能",
    )

    def __init__(self, *args, tree_version, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_parent"].queryset = (
            SkillTreeNode.objects.filter(
                tree_version=tree_version,
            )
            .select_related("skill")
            .order_by("order", "pk")
        )

    def clean_new_parent(self):
        parent = self.cleaned_data["new_parent"]
        return parent


class SkillTreeMoveForm(StyledFormMixin, forms.Form):
    new_parent = forms.ChoiceField(label="目标父技能", required=False)

    def __init__(self, *args, tree_version, node, **kwargs):
        super().__init__(*args, **kwargs)
        nodes = list(
            SkillTreeNode.objects.filter(tree_version=tree_version).select_related("skill").order_by("order", "pk")
        )
        node_by_id = {item.pk: item for item in nodes}
        children_by_parent = {}
        for item in nodes:
            children_by_parent.setdefault(item.parent_id, []).append(item)
        excluded_ids = set()
        stack = [node.pk]
        while stack:
            current = stack.pop()
            excluded_ids.add(current)
            stack.extend(child.pk for child in children_by_parent.get(current, ()))

        path_cache = {}

        def path_for(item):
            if item.pk in path_cache:
                return path_cache[item.pk]
            parts = [item.skill.name]
            parent_id = item.parent_id
            while parent_id is not None:
                parent = node_by_id[parent_id]
                parts.append(parent.skill.name)
                parent_id = parent.parent_id
            path_cache[item.pk] = " / ".join(reversed(parts))
            return path_cache[item.pk]

        self.fields["new_parent"].choices = [
            ("", "作为根技能"),
            *[(str(item.pk), path_for(item)) for item in nodes if item.pk not in excluded_ids],
        ]


class SkillTreeRemoveForm(StyledFormMixin, forms.Form):
    mode = forms.ChoiceField(
        label="移除方式",
        choices=(
            ("promote_children", "仅移除当前技能，并将子技能提升一级（推荐）"),
            ("subtree", "移除整个分支"),
        ),
        widget=forms.RadioSelect,
    )
    confirm_subtree = forms.BooleanField(label="我确认移除整个分支", required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("mode") == "subtree" and not cleaned.get("confirm_subtree"):
            self.add_error("confirm_subtree", "移除整个分支前必须再次确认。")
        return cleaned


class WSOSVersionForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WSOSVersion
        fields = ["skill_project", "code", "name", "description", "is_current"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class WSOSSectionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = WSOSSection
        fields = ["code", "name", "description", "weight", "order"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class SkillWSOSMapForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SkillWSOSMap
        fields = ["skill", "wsos_section", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}


class SkillWSOSMapNoteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SkillWSOSMap
        fields = ["note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}
