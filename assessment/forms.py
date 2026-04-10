from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator

from core.utils.forms import StyledFormMixin
from core.utils.validators import validate_file_size
from core.constants import (
    ASSESSMENT_TP_ALLOWED_EXTENSIONS,
    ASSESSMENT_TP_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_MC_ALLOWED_EXTENSIONS,
    ASSESSMENT_MC_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_MT_ALLOWED_EXTENSIONS,
    ASSESSMENT_MT_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_MS_ALLOWED_EXTENSIONS,
    ASSESSMENT_MS_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_ATTACHMENT_ALLOWED_EXTENSIONS,
    ASSESSMENT_ATTACHMENT_UPLOAD_MAX_SIZE_MB,
)
from .models import AssessmentModule, Score


User = get_user_model()


def _accept_attr(allowed_extensions: list[str]) -> str:
    return ",".join(f".{ext}" for ext in allowed_extensions)


class MultipleFileInput(forms.ClearableFileInput):
    """
    支持多文件上传的自定义widget, 目前官方提供的方法
    "Django 有可能在未来的某个时候提供适当的多文件字段支持。"
    """
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """
    支持多文件上传的自定义字段
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class AssessmentFileUploadForm(StyledFormMixin, forms.ModelForm):
    """考核资料上传表单"""

    # 使用官方推荐的多文件上传方式
    attachments = MultipleFileField(
        widget=MultipleFileInput(attrs={
            "type": "file",
            "aria-label": "file-input",
            "accept": _accept_attr(ASSESSMENT_ATTACHMENT_ALLOWED_EXTENSIONS),
        }),
        required=False,
        label="附件文件",
        help_text=(
            "可上传多个附件文件，支持 "
            f"{', '.join(ASSESSMENT_ATTACHMENT_ALLOWED_EXTENSIONS)}，"
            f"单个文件不超过 {ASSESSMENT_ATTACHMENT_UPLOAD_MAX_SIZE_MB}MB"
        ),
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
                "accept": _accept_attr(ASSESSMENT_TP_ALLOWED_EXTENSIONS),
            }),
            "scoring_standard_file": forms.FileInput(attrs={
                "accept": _accept_attr(ASSESSMENT_MC_ALLOWED_EXTENSIONS),
            }),
            "scoring_sheet_file": forms.FileInput(attrs={
                "accept": _accept_attr(ASSESSMENT_MT_ALLOWED_EXTENSIONS),
            }),
            "scoring_script_file": forms.FileInput(attrs={
                "accept": _accept_attr(ASSESSMENT_MS_ALLOWED_EXTENSIONS),
            }),
        }

    def clean_question_file(self):
        file = self.cleaned_data.get("question_file")
        if file:
            validate_file_size(file, ASSESSMENT_TP_UPLOAD_MAX_SIZE_MB)
        return file

    def clean_scoring_standard_file(self):
        file = self.cleaned_data.get("scoring_standard_file")
        if file:
            validate_file_size(file, ASSESSMENT_MC_UPLOAD_MAX_SIZE_MB)
        return file

    def clean_scoring_sheet_file(self):
        file = self.cleaned_data.get("scoring_sheet_file")
        if file:
            validate_file_size(file, ASSESSMENT_MT_UPLOAD_MAX_SIZE_MB)
        return file

    def clean_scoring_script_file(self):
        file = self.cleaned_data.get("scoring_script_file")
        if file:
            validate_file_size(file, ASSESSMENT_MS_UPLOAD_MAX_SIZE_MB)
        return file

    def clean_attachments(self):
        files = self.cleaned_data.get("attachments")
        if not files:
            return files
        if not isinstance(files, (list, tuple)):
            files = [files]
        ext_validator = FileExtensionValidator(
            allowed_extensions=ASSESSMENT_ATTACHMENT_ALLOWED_EXTENSIONS
        )
        for file in files:
            ext_validator(file)
            validate_file_size(file, ASSESSMENT_ATTACHMENT_UPLOAD_MAX_SIZE_MB)
        return files


class ModuleScoreBatchForm(StyledFormMixin, forms.Form):
    """批量录入某模块所有参考人员成绩的表单"""

    def __init__(self, *args, assessment_module, **kwargs):
        self.assessment_module = assessment_module
        super().__init__(*args, **kwargs)
        participants = assessment_module.assessment.participants.all().order_by(
            "last_name", "first_name", "username"
        )
        existing_scores = {
            s.user_id: s.score
            for s in assessment_module.scores.all()
        }
        for participant in participants:
            field_name = f"score_{participant.pk}"
            self.fields[field_name] = forms.DecimalField(
                label=participant.display_name,
                max_digits=5,
                decimal_places=2,
                min_value=Decimal("0.00"),
                required=False,
                initial=existing_scores.get(participant.pk),
                widget=forms.NumberInput(attrs={
                    "step": "0.01",
                    "min": "0",
                    "max": str(assessment_module.max_score),
                    "placeholder": f"满分 {assessment_module.max_score}",
                    "class": "input w-full",
                }),
            )

    def score_fields(self):
        for name, field in self.fields.items():
            if name.startswith("score_"):
                yield self[name]

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
        for name, value in self.cleaned_data.items():
            if not name.startswith("score_"):
                continue
            user_id = int(name.split("_", 1)[1])
            if value is None:
                continue
            obj, _ = Score.objects.update_or_create(
                assessment_module=self.assessment_module,
                user_id=user_id,
                defaults={"score": value},
            )
            saved.append(obj)
        return saved
