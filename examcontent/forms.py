from __future__ import annotations

from django import forms

from core.utils.forms import StyledFormMixin

from .models import ExamPaper, ExamRequirement


class ExamPaperForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ExamPaper
        fields = ["event_module", "source_asset", "title", "version", "language", "status"]


class ExamRequirementForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ExamRequirement
        fields = [
            "paper",
            "capability_domain",
            "code",
            "title",
            "original_text",
            "normalized_text",
            "requirement_type",
            "source_location",
            "estimated_difficulty",
            "is_explicitly_marked",
            "extraction_source",
        ]
        widgets = {
            "original_text": forms.Textarea(attrs={"rows": 4}),
            "normalized_text": forms.Textarea(attrs={"rows": 4}),
        }
