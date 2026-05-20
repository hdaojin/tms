from django import forms

from .models import Meeting

from core.uploads import MEETING_FILE_UPLOAD_SPEC
from core.utils.forms import DefaultTodayDateFormMixin, StyledFormMixin


class MeetingUploadForm(DefaultTodayDateFormMixin, StyledFormMixin, forms.ModelForm):
    default_today_date_fields = ('date',)

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
