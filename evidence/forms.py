from django import forms
from django.db.models import Q

from assessments.models import AssessmentDocument
from assessments.selectors import assessment_modules_in_scope_for
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

    def __init__(self, *args, user=None, permission="evidence.add_knowledgeevidence", **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            return
        modules = assessment_modules_in_scope_for(user, permission)
        project_ids = modules.values("assessment__skill_project_id")
        self.fields["assessment_module"].queryset = modules.select_related("assessment")
        self.fields["skill_project"].queryset = self.fields["skill_project"].queryset.filter(pk__in=project_ids)
        self.fields["source_document"].queryset = AssessmentDocument.objects.filter(
            Q(module__in=modules) | Q(module__isnull=True, assessment__skill_project_id__in=project_ids)
        ).distinct()


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
