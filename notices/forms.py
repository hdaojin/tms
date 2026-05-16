from django import forms
from .models import Notice, NoticeAttachment
from core.forms.fields import MultipleFileField, MultipleFileInput
from core.uploads import NOTICE_ATTACHMENT_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin


class NoticeForm(StyledFormMixin, forms.ModelForm):
    """
    通知创建和编辑表单
    """
    # 添加"所有人"选项，默认勾选
    send_to_all = forms.BooleanField(
        required=False,
        initial=True,
        label='所有人',
        help_text='勾选后将向所有用户发送通知'
    )
    
    attachments = MultipleFileField(
        upload_spec=NOTICE_ATTACHMENT_UPLOAD_SPEC,
        widget=MultipleFileInput(attrs={
            'type': 'file',
            'aria-label': 'file-input',
            'class': 'file-input w-full file-input-primary',
        }),
        required=False,
        label='附件',
        help_text=NOTICE_ATTACHMENT_UPLOAD_SPEC.help_text('支持多个文件上传')
    )


    class Meta:
        model = Notice
        fields = ['title', 'content', 'attachments', 'send_to_all', 'target_groups']
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
            'target_groups': '指定用户组',
        }
        help_texts = {
            'title': '留空将显示为"无标题"',
            'content': '支持换行和简单格式',
            'target_groups': '勾选"所有人"时此项无效；取消"所有人"后可选择特定用户组',
        }


    def save(self, commit=True):
        notice = super().save(commit=False)
        
        # 设置发布时间（统一立即发布）
        if not notice.published_at:
            from django.utils import timezone
            notice.published_at = timezone.now()
        
        if commit:
            notice.save()
            
            # 处理目标用户组：如果勾选"所有人"，清空 target_groups
            if self.cleaned_data.get('send_to_all'):
                notice.target_groups.clear()
            else:
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
                **NOTICE_ATTACHMENT_UPLOAD_SPEC.widget_attrs(),
            })
        }
