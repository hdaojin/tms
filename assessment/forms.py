from django import forms
from core.utils.forms import StyledFormMixin
from core.constants import ASSESSMENT_ALLOWED_EXTENSIONS
from .models import AssessmentModule


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
            'type': 'file',
            'aria-label': 'file-input',
            'accept': ','.join(['.' + ext for ext in ASSESSMENT_ALLOWED_EXTENSIONS]),
        }),
        required=False,
        label='附件文件',
        help_text='可上传多个附件文件'
    )
    
    class Meta:
        model = AssessmentModule
        fields = [
            'question_file',
            'scoring_standard_file', 
            'scoring_sheet_file',
            'scoring_script_file',
        ]
        widgets = {
            'question_file': forms.FileInput(attrs={
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.zip',
            }),
            'scoring_standard_file': forms.FileInput(attrs={
                'accept': '.pdf,.doc,.docx,.xls,.xlsx',
            }),
            'scoring_sheet_file': forms.FileInput(attrs={
                'accept': '.pdf,.xls,.xlsx',
            }),
            'scoring_script_file': forms.FileInput(attrs={
                'accept': '.py,.sh,.zip',
            }),
        }
