from __future__ import annotations

from django import forms

from assessments.models import AssessmentDocument
from core.utils.forms import StyledFormMixin

from .models import ScoringParserConfig, ScoringParticipant, ScoringResult
from .services import default_parser_config, enabled_parser_configs


class AssessmentDocumentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.assessment.name} / {obj.module.code} - {obj.title}"


class ParserConfigChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.display_name


class ScoringImportForm(StyledFormMixin, forms.Form):
    source_document = AssessmentDocumentChoiceField(label="评分表资料", queryset=AssessmentDocument.objects.none())
    parser_config = ParserConfigChoiceField(
        label="解析器", queryset=ScoringParserConfig.objects.none(), help_text="只显示已启用的评分表解析器。"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        documents = (
            AssessmentDocument.objects.filter(
                document_type=AssessmentDocument.DocumentType.MARKING_SCHEME, module__isnull=False
            )
            .select_related("assessment", "module")
            .order_by("-assessment__start_date", "assessment__name", "module__order")
        )
        self.fields["source_document"].queryset = documents
        self.fields["parser_config"].queryset = enabled_parser_configs()
        if not self.is_bound:
            self.fields["source_document"].initial = getattr(documents.first(), "pk", None)
            self.fields["parser_config"].initial = getattr(default_parser_config(), "pk", None)


class ScoringParticipantForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ScoringParticipant
        fields = [
            "scheme",
            "assessment_participant",
            "user",
            "external_identifier",
            "display_name",
            "organization",
            "order",
        ]


class ScoringResultForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ScoringResult
        fields = ["participant", "aspect", "score_awarded", "source", "evidence", "graded_at"]
        widgets = {
            "graded_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "evidence": forms.Textarea(attrs={"rows": 3}),
        }
