from django import forms

from core.forms.fields import MultipleFileField, MultipleFileInput
from core.uploads import (
    ASSESSMENT_ATTACHMENT_UPLOAD_SPEC,
    ASSESSMENT_MC_UPLOAD_SPEC,
    ASSESSMENT_MS_UPLOAD_SPEC,
    ASSESSMENT_MT_UPLOAD_SPEC,
    ASSESSMENT_TP_UPLOAD_SPEC,
)
from core.utils.forms import StyledFormMixin
from .models import AssessmentModule


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

