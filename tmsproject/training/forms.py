from django import forms
from .models import TrainingLog
from django.core.exceptions import ValidationError
import datetime  # 新增导入

class TrainingLogUploadForm(forms.ModelForm):
    class Meta:
        model = TrainingLog
        fields = ['module', 'training_date', 'task', 'upload']
        widgets = {
            'training_date': forms.DateInput(attrs={'type': 'date'}),
        }
    

    def clean(self):
        cleaned_data = super().clean()
        upload = cleaned_data.get('upload')
        training_date = cleaned_data.get('training_date')
        
        # 验证训练日期不能大于当前日期
        if training_date and training_date > datetime.date.today():
            raise ValidationError({"training_date": "训练日期不能大于当前日期"})
            
        if upload:
            if upload.size > 1024 * 1024 * 10:
                raise ValidationError("上传文件大小不能超过10MB")
            valid_extensions = ['.doc', '.docx', '.pdf']
            if not any(upload.name.lower().endswith(ext) for ext in valid_extensions):
                raise ValidationError("上传文件格式必须为doc、docx或pdf")
        return cleaned_data