from django import forms
from .models import Notice, NoticeAttachment, ALLOWED_EXTENSIONS
from core.utils.forms import StyledFormMixin


class MultipleFileInput(forms.ClearableFileInput):
    """
    支持多文件上传的自定义widget, 目前官方提供的方法
    “Django 有可能在未来的某个时候提供适当的多文件字段支持。”
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


class NoticeForm(StyledFormMixin, forms.ModelForm):
    """
    通知创建和编辑表单
    """
    attachments = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'type': 'file',
            'aria-label': 'file-input',
            'class': 'file-input w-full file-input-primary',
            'accept': ','.join(['.' + ext for ext in ALLOWED_EXTENSIONS]),
        }),
        required=False,
        label='附件',
        help_text='支持多个文件上传，支持格式：PDF、Word、图片、压缩包等'
    )


    class Meta:
        model = Notice
        fields = ['title', 'content', 'attachments', 'target_groups']
        widgets = {
            'title': forms.TextInput(attrs={
                'type': 'text',
                'aria-label': 'title-input',
                'placeholder': '请输入通知标题（可选）'
            }),
            'content': forms.Textarea(attrs={
                'type': 'text',
                'aria-label': 'content-input',
                'placeholder': '请输入通知内容...',
                # 'rows': 8
            }),
            'target_groups': forms.CheckboxSelectMultiple(attrs={
                'type': 'checkbox',
                'aria-label': 'target-groups-input',
            }),
        }
        labels = {
            'title': '通知标题',
            'content': '通知内容',
            'target_groups': '目标用户组',
        }
        help_texts = {
            'title': '留空将显示为"无标题"',
            'content': '支持换行和简单格式',
            'target_groups': '不选择任何组将向所有用户发送',
        }


    def save(self, commit=True):
        notice = super().save(commit=False)
        
        # 设置发布时间（统一立即发布）
        if not notice.published_at:
            from django.utils import timezone
            notice.published_at = timezone.now()
        
        if commit:
            notice.save()
            self.save_m2m()  # 保存多对多关系
        
        return notice


class NoticeAttachmentForm(forms.ModelForm):
    """
    附件表单（用于内联编辑）
    """
    class Meta:
        model = NoticeAttachment
        fields = ['file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={
                'class': 'file-input file-input-bordered file-input-sm w-full',
                'accept': '.pdf,.doc,.docx,.txt,.jpg,.jpeg,.png,.gif,.zip,.rar'
            })
        }
