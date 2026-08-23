from django import forms
from core.utils.forms import StyledFormMixin
from standards.forms import DefaultSkillProjectFormMixin
from standards.models import Skill
from .models import EvidenceSkillMap, KnowledgeEvidence


class KnowledgeEvidenceForm(DefaultSkillProjectFormMixin, StyledFormMixin, forms.ModelForm):
    class Meta:
        model = KnowledgeEvidence
        fields = [
            "skill_project",
            "assessment_module",
            "source_type",
            "source_document",
            "title",
            "original_text",
            "normalized_text",
            "source_location",
            "estimated_mark",
            "estimated_difficulty",
            "evidence_level",
            "confidence",
            "review_note",
        ]
        widgets = {
            "original_text": forms.Textarea(attrs={"rows": 4}),
            "normalized_text": forms.Textarea(attrs={"rows": 4}),
            "review_note": forms.Textarea(attrs={"rows": 3}),
        }


class KnowledgeEvidenceRejectForm(StyledFormMixin, forms.Form):
    review_note = forms.CharField(label="拒绝原因", widget=forms.Textarea(attrs={"rows": 4}))


class EvidenceSkillMapForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EvidenceSkillMap
        fields = ["evidence", "skill", "is_primary", "weight", "mapping_source", "confidence", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        evidence = kwargs.pop("evidence", None)
        super().__init__(*args, **kwargs)
        if evidence:
            self.fields["evidence"].queryset = KnowledgeEvidence.objects.filter(pk=evidence.pk)
            self.fields["evidence"].initial = evidence
            self.fields["skill"].queryset = Skill.objects.filter(skill_project=evidence.skill_project, is_active=True)
