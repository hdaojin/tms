from django import forms
from django.forms import inlineformset_factory
from core.utils.forms import StyledFormMixin
from .models import AssessmentModule, AssessmentAttachment


class AssessmentFileUploadForm(StyledFormMixin, forms.ModelForm):
    """考核资料上传表单"""
    
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


# 附件表单集 - 支持上传多个附件
AttachmentFormSet = inlineformset_factory(
    AssessmentModule,
    AssessmentAttachment,
    fields=['file', 'description'],
    extra=3,  # 默认显示3个空表单
    can_delete=True,
    widgets={
        'file': forms.FileInput(attrs={
            'class': 'file-input file-input-bordered w-full',
        }),
        'description': forms.TextInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': '文件说明（可选）'
        }),
    }
)
