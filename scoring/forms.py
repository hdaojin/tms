from __future__ import annotations

from django import forms

from assessments.models import AssessmentDocument, AssessmentParticipant, CompetitionRole
from core.utils.forms import StyledFormMixin

from .models import ScoringAspect, ScoringParserConfig, ScoringResult
from .selectors import scoring_modules_in_scope_for, scoring_scheme_documents_in_scope_for
from .services import default_parser_config, enabled_parser_configs


class AssessmentDocumentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        label = f"{obj.assessment.name} / {obj.module.code} - {obj.title}"
        return f"{label}（{obj.version}）" if obj.version else label


class ParserConfigChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.display_name


class ScoringImportForm(StyledFormMixin, forms.Form):
    source_document = AssessmentDocumentChoiceField(label="评分标准资料", queryset=AssessmentDocument.objects.none())
    parser_config = ParserConfigChoiceField(
        label="解析器", queryset=ScoringParserConfig.objects.none(), help_text="只显示已启用的评分标准解析器。"
    )

    def __init__(self, *args, user=None, permission="scoring.add_scoringscheme", module_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        documents = AssessmentDocument.objects.filter(
            document_type=AssessmentDocument.DocumentType.MARKING_STANDARD,
            module__isnull=False,
        )
        if user is not None:
            documents = scoring_scheme_documents_in_scope_for(user, permission, documents)
        if module_id and str(module_id).isdigit():
            documents = documents.filter(module_id=module_id)
        documents = documents.select_related("assessment", "module").order_by(
            "-assessment__start_date",
            "assessment__name",
            "module__order",
        )
        self.fields["source_document"].queryset = documents
        self.fields["parser_config"].queryset = enabled_parser_configs()
        if not self.is_bound:
            self.fields["source_document"].initial = getattr(documents.first(), "pk", None)
            self.fields["parser_config"].initial = getattr(default_parser_config(), "pk", None)


class ScoringResultForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ScoringResult
        fields = ["participant", "aspect", "score_awarded", "evidence"]
        widgets = {"evidence": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, permission="scoring.add_scoringresult", **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            return
        modules = scoring_modules_in_scope_for(user, permission)
        self.fields["aspect"].queryset = ScoringAspect.objects.filter(
            scheme__assessment_module__in=modules
        ).select_related("scheme", "scheme__assessment_module")
        self.fields["participant"].queryset = AssessmentParticipant.objects.filter(
            assessment_id__in=modules.values("assessment_id"),
            role__category=CompetitionRole.Category.COMPETITOR,
        ).select_related("assessment", "role")


class OnlineScoringForm(StyledFormMixin, forms.Form):
    score_awarded = forms.DecimalField(label="得分", min_value=0, max_digits=8, decimal_places=2)
    evidence = forms.CharField(
        label="证据摘要",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    confirm = forms.BooleanField(label="确认本项得分", required=False)
    reason = forms.CharField(label="修改原因", required=False, max_length=255)

    def __init__(self, *args, aspect, result=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.aspect = aspect
        self.fields["score_awarded"].max_value = aspect.max_mark
        self.fields["score_awarded"].widget.attrs.update({"max": str(aspect.max_mark), "step": "0.01"})
        if result is not None and not self.is_bound:
            self.initial.update(
                {
                    "score_awarded": result.score_awarded,
                    "evidence": result.evidence,
                    "confirm": bool(result.confirmed_at),
                }
            )

    def clean_score_awarded(self):
        score = self.cleaned_data["score_awarded"]
        if score > self.aspect.max_mark:
            raise forms.ValidationError(f"得分不能超过评分点分值 {self.aspect.max_mark}。")
        return score
