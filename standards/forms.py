from __future__ import annotations

from django import forms

from core.utils.forms import StyledFormMixin

from .models import CapabilityDomain, SkillNode, SkillProject, SkillTreeVersion


class SkillProjectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SkillProject
        fields = ["code", "name", "short_name", "description", "order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class CapabilityDomainForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CapabilityDomain
        fields = ["skill_project", "code", "name", "description", "order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class SkillTreeVersionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SkillTreeVersion
        fields = ["skill_project", "version", "name", "description", "is_current"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def _post_clean(self):
        requested_current = self.cleaned_data.get("is_current")
        if requested_current:
            self.cleaned_data["is_current"] = False
            self.instance.is_current = False
        try:
            super()._post_clean()
        finally:
            if requested_current:
                self.cleaned_data["is_current"] = True
                self.instance.is_current = True


class SkillNodeForm(StyledFormMixin, forms.ModelForm):
    tags_text = forms.CharField(label="标签", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    aliases_text = forms.CharField(label="别名", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    class Meta:
        model = SkillNode
        fields = [
            "tree_version",
            "capability_domain",
            "parent",
            "node_type",
            "code",
            "name",
            "description",
            "difficulty",
            "is_core",
            "is_assessable",
            "order",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["tags_text"].initial = "\n".join(self.instance.tags or [])
            self.fields["aliases_text"].initial = "\n".join(self.instance.aliases or [])
        tree_version = self.initial.get("tree_version") or getattr(self.instance, "tree_version", None)
        if tree_version:
            self.fields["capability_domain"].queryset = CapabilityDomain.objects.filter(skill_project=tree_version.skill_project)
            self.fields["parent"].queryset = SkillNode.objects.filter(tree_version=tree_version).exclude(pk=self.instance.pk)

    @staticmethod
    def _split_text(value):
        return [item.strip() for item in (value or "").replace(",", "\n").splitlines() if item.strip()]

    def save(self, commit=True):
        self.instance.tags = self._split_text(self.cleaned_data.get("tags_text"))
        self.instance.aliases = self._split_text(self.cleaned_data.get("aliases_text"))
        return super().save(commit=commit)
