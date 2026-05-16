from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from core.forms.fields import MultipleFileField, MultipleFileInput
from core.uploads import (
    ASSESSMENT_ATTACHMENT_UPLOAD_SPEC,
    ASSESSMENT_MC_UPLOAD_SPEC,
    ASSESSMENT_MS_UPLOAD_SPEC,
    ASSESSMENT_MT_UPLOAD_SPEC,
    ASSESSMENT_TP_UPLOAD_SPEC,
)
from core.utils.forms import StyledFormMixin
from .models import AssessmentModule, Score


User = get_user_model()


class AssessmentFileUploadForm(StyledFormMixin, forms.ModelForm):
    """考核资料上传表单"""

    attachments = MultipleFileField(
        upload_spec=ASSESSMENT_ATTACHMENT_UPLOAD_SPEC,
        widget=MultipleFileInput(attrs={
            "type": "file",
            "aria-label": "file-input",
        }),
        required=False,
        label="试题附件",
        help_text=ASSESSMENT_ATTACHMENT_UPLOAD_SPEC.help_text("可上传多个试题附件"),
    )

    class Meta:
        model = AssessmentModule
        fields = [
            "question_file",
            "scoring_standard_file",
            "scoring_sheet_file",
            "scoring_script_file",
        ]
        widgets = {
            "question_file": forms.FileInput(attrs={
                **ASSESSMENT_TP_UPLOAD_SPEC.widget_attrs(),
            }),
            "scoring_standard_file": forms.FileInput(attrs={
                **ASSESSMENT_MC_UPLOAD_SPEC.widget_attrs(),
            }),
            "scoring_sheet_file": forms.FileInput(attrs={
                **ASSESSMENT_MT_UPLOAD_SPEC.widget_attrs(),
            }),
            "scoring_script_file": forms.FileInput(attrs={
                **ASSESSMENT_MS_UPLOAD_SPEC.widget_attrs(),
            }),
        }


class ModuleScoreBatchForm(StyledFormMixin, forms.Form):
    """批量录入某模块所有参考人员成绩的表单"""

    def __init__(self, *args, assessment_module, **kwargs):
        self.assessment_module = assessment_module
        super().__init__(*args, **kwargs)
        participants = assessment_module.assessment.participants.all().order_by(
            "last_name", "first_name", "username"
        )
        existing_scores = {
            s.user_id: s
            for s in assessment_module.scores.all()
        }
        self.participants = list(participants)
        for participant in self.participants:
            existing_score = existing_scores.get(participant.pk)
            score_field_name = f"score_{participant.pk}"
            remarks_field_name = f"remarks_{participant.pk}"
            self.fields[score_field_name] = forms.DecimalField(
                label=participant.display_name,
                max_digits=5,
                decimal_places=2,
                min_value=Decimal("0.00"),
                required=False,
                initial=existing_score.score if existing_score else None,
                widget=forms.NumberInput(attrs={
                    "step": "0.01",
                    "min": "0",
                    "max": str(assessment_module.max_score),
                    "placeholder": f"满分 {assessment_module.max_score}",
                    "class": "input w-full",
                }),
            )
            self.fields[remarks_field_name] = forms.CharField(
                label=f"{participant.display_name}备注",
                required=False,
                initial=existing_score.remarks if existing_score else "",
                widget=forms.TextInput(attrs={
                    "placeholder": "备注（可选）",
                    "class": "input w-full",
                }),
            )

    def score_rows(self):
        for participant in self.participants:
            yield {
                "participant": participant,
                "score": self[f"score_{participant.pk}"],
                "remarks": self[f"remarks_{participant.pk}"],
            }

    def clean(self):
        cleaned_data = super().clean()
        max_score = self.assessment_module.max_score
        for name, value in cleaned_data.items():
            if not name.startswith("score_") or value is None:
                continue
            if value > max_score:
                self.add_error(name, f"分数不能超过满分 {max_score}")
        return cleaned_data

    def save(self):
        saved = []
        existing_scores = {
            score.user_id: score
            for score in self.assessment_module.scores.all()
        }
        for participant in self.participants:
            user_id = participant.pk
            score_value = self.cleaned_data.get(f"score_{user_id}")
            remarks_value = (self.cleaned_data.get(f"remarks_{user_id}") or "").strip()
            existing_score = existing_scores.get(user_id)
            if score_value is None and not remarks_value:
                continue
            if score_value is None:
                score_value = existing_score.score if existing_score else Decimal("0.00")
            obj, _ = Score.objects.update_or_create(
                assessment_module=self.assessment_module,
                user_id=user_id,
                defaults={
                    "score": score_value,
                    "remarks": remarks_value,
                },
            )
            saved.append(obj)
        return saved
