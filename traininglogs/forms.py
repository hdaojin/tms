from django import forms
from django.utils import timezone

from competitions.models import StandardModule

from .models import TrainingLog
from core.utils.forms import StyledFormMixin
from core.constants import TRAININGLOG_ALLOWED_EXTENSIONS

class TrainingLogCreateForm(StyledFormMixin, forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        self.current_user = user
        super().__init__(*args, **kwargs)
        if self.current_user and not self.instance.uploaded_by_id:
            self.instance.uploaded_by = self.current_user

        module_field = self.fields['module']
        module_field.queryset = StandardModule.objects.current().select_related('project', 'module_set').order_by(
            'project__name',
            'module_set__sort_order',
            'sort_order',
            'code',
            'name',
        )
        module_field.required = True
        module_field.empty_label = None
        module_field.label_from_instance = lambda obj: f"{obj.code} - {obj.name}" #type: ignore
        # 如果需要，可以在这里添加自定义初始化逻辑
        # 例如，动态设置某些字段的选项或初始值
        # 设置默认日期为今天（每次实例化时动态设置）
        if not self.instance.pk:
            today = timezone.localdate()
            self.fields['training_date'].initial = today.strftime('%Y-%m-%d')
            self.fields['training_date'].widget.attrs['value'] = today.strftime('%Y-%m-%d')

    class Meta:
        model = TrainingLog
        fields = ['training_date', 'module', 'task', 'file']
        localized_fields = ['training_date']    # 使用本地化日期输入
        widgets = {
            'training_date': forms.DateInput(attrs={'type': 'date', 'aria-label': 'date-input'}),
            'module': forms.RadioSelect(attrs={'aria-label': 'radio'}),
            'task': forms.TextInput(attrs={'type':'text', 'aria-label': 'input', 'placeholder': '例如: Nginx安装与配置'}),
            'file': forms.ClearableFileInput(attrs={'type':'file', 'aria-label': 'file-input', 'accept': ','.join(['.' + ext for ext in TRAININGLOG_ALLOWED_EXTENSIONS])})
            }

        # labels = {
        #     'training_date': '训练日期',
        #     'module': '训练模块',
        #     'task': '训练任务',
        #     'file': '日志文件',
        # }

