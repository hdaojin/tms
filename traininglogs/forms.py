from django import forms
from django.utils import timezone
from django.conf import settings
from .models import TrainingLog
from common.forms import StyledFormMixin

ALLOWED_EXTENSIONS = getattr(settings, "TRAININGLOG_ALLOWED_EXTENSIONS", ['pdf'])

class TrainingLogCreateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TrainingLog
        fields = ['training_date', 'module', 'task', 'file']
        localized_fields = ['training_date']    # 使用本地化日期输入
        widgets = {
            'training_date': forms.DateInput(attrs={'type': 'date', 'aria-label': 'date-input'}),
            'module': forms.Select(attrs={'type': 'select', 'aria-label': 'select'}),
            'task': forms.TextInput(attrs={'type':'text', 'aria-label': 'input', 'placeholder': '例如: Nginx安装与配置'}),
            'file': forms.ClearableFileInput(attrs={'type':'file', 'aria-label': 'file-input', 'accept': ','.join(['.' + ext for ext in ALLOWED_EXTENSIONS])})
            }

        # labels = {
        #     'training_date': '训练日期',
        #     'module': '训练模块',
        #     'task': '训练任务',
        #     'file': '日志文件',
        # }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 如果需要，可以在这里添加自定义初始化逻辑
        # 例如，动态设置某些字段的选项或初始值
        # 设置默认日期为今天（每次实例化时动态设置）
        if not self.instance.pk: 
            today = timezone.localdate()
            self.fields['training_date'].initial = today.strftime('%Y-%m-%d')
            self.fields['training_date'].widget.attrs['value'] = today.strftime('%Y-%m-%d')