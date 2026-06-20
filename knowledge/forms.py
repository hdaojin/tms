from __future__ import annotations

from django import forms

from core.utils.forms import StyledFormMixin
from standards.models import SkillNode

from .models import KnowledgeEvidence, KnowledgeEvidenceSkillMap


class KnowledgeEvidenceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = KnowledgeEvidence
        fields = [
            "skill_project",
            "event_module",
            "capability_domain",
            "source_type",
            "title",
            "original_text",
            "normalized_text",
            "estimated_mark",
            "estimated_difficulty",
            "evidence_level",
            "extraction_source",
            "confidence",
            "review_status",
            "review_note",
        ]
        widgets = {
            "original_text": forms.Textarea(attrs={"rows": 4}),
            "normalized_text": forms.Textarea(attrs={"rows": 4}),
            "review_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["source_type"].initial = KnowledgeEvidence.SourceType.MANUAL
            self.fields["extraction_source"].initial = KnowledgeEvidence.ExtractionSource.MANUAL
            self.fields["review_status"].initial = KnowledgeEvidence.ReviewStatus.APPROVED
            self.fields["confidence"].initial = 1.0

    def clean(self):
        cleaned = super().clean()
        event_module = cleaned.get("event_module")
        skill_project = cleaned.get("skill_project")
        capability_domain = cleaned.get("capability_domain")
        if event_module and skill_project and event_module.event.skill_project_id != skill_project.pk:
            self.add_error("skill_project", "技能项目必须与事件模块所属技能项目一致。")
        if capability_domain and skill_project and capability_domain.skill_project_id != skill_project.pk:
            self.add_error("capability_domain", "能力领域必须属于当前技能项目。")
        return cleaned


class KnowledgeEvidenceRejectForm(StyledFormMixin, forms.Form):
    review_note = forms.CharField(label="拒绝原因", widget=forms.Textarea(attrs={"rows": 4}))


class KnowledgeEvidenceSkillMapForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = KnowledgeEvidenceSkillMap
        fields = ["evidence", "skill_node", "is_primary", "weight", "mapping_source", "confidence", "reason", "review_status"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        evidence = kwargs.pop("evidence", None)
        super().__init__(*args, **kwargs)
        if evidence is not None:
            self.fields["evidence"].initial = evidence
            self.fields["evidence"].queryset = KnowledgeEvidence.objects.filter(pk=evidence.pk)
            qs = SkillNode.objects.filter(
                tree_version__skill_project=evidence.skill_project,
                tree_version__is_current=True,
                node_type=SkillNode.NodeType.SKILL,
                is_active=True,
            )
            if evidence.capability_domain_id:
                qs = qs.filter(capability_domain=evidence.capability_domain)
            self.fields["skill_node"].queryset = qs.select_related("tree_version", "capability_domain")
        else:
            self.fields["skill_node"].queryset = SkillNode.objects.filter(
                tree_version__is_current=True,
                node_type=SkillNode.NodeType.SKILL,
                is_active=True,
            )
        if not self.instance.pk:
            self.fields["mapping_source"].initial = KnowledgeEvidenceSkillMap.MappingSource.MANUAL
            self.fields["review_status"].initial = KnowledgeEvidence.ReviewStatus.APPROVED
            self.fields["confidence"].initial = 1.0
