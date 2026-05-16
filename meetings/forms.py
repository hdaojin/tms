from django import forms
from .models import Meeting
from django.utils import timezone

from core.uploads import MEETING_FILE_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin

class MeetingUploadForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['title', 'date', 'file']
        localized_fields = ['date']    # 使用本地化日期输入
        widgets = {
            'title': forms.TextInput(attrs={'type': 'text', 'aria-label': 'title-input', 'placeholder': '例如: 网络系统管理项目周例会'}),
            'date': forms.DateInput(attrs={'type': 'date', 'aria-label': 'date-input'}),
            'file': forms.FileInput(attrs=MEETING_FILE_UPLOAD_SPEC.widget_attrs(
                type='file',
                **{'aria-label': 'file-input'},
            )),
         }
        labels = {
            'title': '会议名称',
            'date': '会议日期',
            'file': '会议记录文件',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 设置默认日期为今天（每次实例化时动态设置）
        if not self.instance.pk: 
            today = timezone.localdate()
            self.fields['date'].initial = today.strftime('%Y-%m-%d')
            self.fields['date'].widget.attrs['value'] = today.strftime('%Y-%m-%d')
