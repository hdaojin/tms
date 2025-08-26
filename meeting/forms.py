from django import forms
from .models import Meeting
from django.core.exceptions import ValidationError
from django.utils import timezone


class MeetingUploadForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['title', 'date', 'upload']
        # 使用自定义的模板filters来渲染样式，所以这里不需要再定义widgets
        # widgets = {
        #     'title': forms.TextInput(attrs={'type': 'text', 'class': 'input input-bordered w-full', 'aria-label': 'input', 'placeholder': '网络系统管理项目周例会'}),
        #     'date': forms.DateInput(attrs={'type': 'date', 'class': 'input input-bordered w-full'}),
        #     'upload': forms.FileInput(attrs={'type':'file', 'class': 'input input-bordered w-full', 'accept': '.pdf', 'aria-label': 'file-input'}),
        # }
        # labels = {
        #     'title': '会议标题',
        #     'date': '会议日期',
        #     'upload': '会议记录文件',
        # }
        # help_texts = {
        #     'upload': '仅支持PDF格式，文件大小不超过10MB',
        # }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 设置字段属性
        self.fields['title'].widget.attrs.update({
            'placeholder': '例如：网络系统管理项目周例会',
        })
        
        self.fields['upload'].widget.attrs.update({
            'accept': '.pdf',
        })
        
        # 设置默认日期为今天（每次实例化时动态设置）
        if not self.instance.pk:
            today = timezone.now().date()
            self.fields['date'].initial = today
            # 同时在widget上设置value属性，确保浏览器显示
            self.fields['date'].widget.attrs['value'] = today.strftime('%Y-%m-%d')

    def clean_upload(self):
        upload = self.cleaned_data.get('upload')
        
        if upload:
            # 检查文件扩展名
            valid_extensions = ['.pdf']
            if not any(upload.name.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError(f"上传文件格式必须为{', '.join(valid_extensions)}。")
            
            # 检查文件大小（10MB = 10 * 1024 * 1024 bytes）
            if upload.size > 10 * 1024 * 1024:
                raise ValidationError('上传文件大小不能超过10MB。')
        
        return upload

    def clean_date(self):
        date = self.cleaned_data.get('date')
        
        if date and date > timezone.now().date():
            raise ValidationError('会议日期不能是未来的日期。')
        
        return date
