from django import forms
from .models import TrainingLog
from django.core.exceptions import ValidationError
import datetime  # 新增导入

class TrainingLogUploadForm(forms.ModelForm):
    class Meta:
        model = TrainingLog
        fields = ['module', 'training_date', 'task', 'upload']
        widgets = {
            'module': forms.Select(attrs={'class': 'select appearance-none', 'aria-label': 'select'}),
            'training_date': forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
            'task': forms.TextInput(attrs={'type':'text', 'class': 'input', 'aria-label': 'input'}),
            'upload': forms.ClearableFileInput(attrs={'type':'file', 'class': 'input', 'aria-label': 'file-input'}),
        }

    def clean_training_date(self):
        """单独验证训练日期字段"""
        training_date = self.cleaned_data.get('training_date')
        
        # 验证训练日期不能大于当前日期,且必须是在当前月份
        if training_date and training_date.month != datetime.date.today().month:
            raise ValidationError("训练日期必须在当前月份")
        if training_date and training_date > datetime.date.today():
            raise ValidationError("训练日期不能大于当前日期")
        
        return training_date
        
    def clean_upload(self):
        """单独验证上传文件字段，这样错误会正确绑定到此字段"""
        upload = self.cleaned_data.get('upload')
        
        # 验证上传文件大小和格式    
        if upload:
            if upload.size > 1024 * 1024 * 10:
                raise ValidationError("上传文件大小不能超过10MB")
            valid_extensions = ['.doc', '.docx', '.pdf']
            if not any(upload.name.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError("上传文件格式必须为doc、docx或pdf")
        return upload