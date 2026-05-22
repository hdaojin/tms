from django import forms

from competition_standards.models import StandardModule, TrainingCycle

from .models import TrainingLog
from core.uploads import TRAININGLOG_UPLOAD_SPEC
from core.utils.forms import DefaultTodayDateFormMixin, StyledFormMixin


def get_training_cycle_modules_queryset(training_cycle):
    if training_cycle is None:
        return StandardModule.objects.none()
    return (
        StandardModule.objects.filter(module_set=training_cycle.module_set)
        .select_related('project', 'module_set')
        .order_by('sort_order', 'code', 'name')
    )


class TrainingLogCreateForm(DefaultTodayDateFormMixin, StyledFormMixin, forms.ModelForm):
    default_today_date_fields = ('training_date',)

    def __init__(self, *args, user=None, **kwargs):
        self.current_user = user
        super().__init__(*args, **kwargs)
        if self.current_user and not self.instance.uploaded_by_id:
            self.instance.uploaded_by = self.current_user

        cycle_field = self.fields['training_cycle']
        cycle_field.queryset = TrainingCycle.objects.select_related(
            'project',
            'module_set',
        ).order_by(
            '-start_date',
            'name',
        )
        cycle_field.empty_label = None
        cycle_field.label_from_instance = lambda obj: f"{obj.name} / {obj.project.name}"  # type: ignore
        if not self.instance.pk and not self.data and cycle_field.queryset.exists():
            self.initial['training_cycle'] = cycle_field.queryset.first()

        selected_training_cycle = self._get_selected_training_cycle(cycle_field.queryset)

        module_field = self.fields['module']
        module_field.queryset = get_training_cycle_modules_queryset(selected_training_cycle)
        module_field.required = True
        module_field.empty_label = None
        module_field.label_from_instance = lambda obj: f"{obj.code} - {obj.name}"  # type: ignore

    class Meta:
        model = TrainingLog
        fields = ['training_cycle', 'training_date', 'module', 'task', 'file']
        localized_fields = ['training_date']    # 使用本地化日期输入
        widgets = {
            'training_cycle': forms.Select(attrs={'aria-label': 'select'}),
            'training_date': forms.DateInput(attrs={'type': 'date', 'aria-label': 'date-input'}),
            'module': forms.RadioSelect(attrs={'aria-label': 'radio'}),
            'task': forms.TextInput(attrs={'type':'text', 'aria-label': 'input', 'placeholder': '例如: Nginx安装与配置'}),
            'file': forms.ClearableFileInput(attrs=TRAININGLOG_UPLOAD_SPEC.widget_attrs(
                type='file',
                **{'aria-label': 'file-input'},
            ))
            }

        # labels = {
        #     'training_cycle': '备赛周期',
        #     'training_date': '训练日期',
        #     'module': '训练模块',
        #     'task': '训练任务',
        #     'file': '日志文件',
        # }

    def _get_selected_training_cycle(self, queryset):
        value = None
        if self.data:
            value = self.data.get(self.add_prefix('training_cycle'))
        elif self.instance.pk and self.instance.training_cycle_id:
            value = self.instance.training_cycle_id
        else:
            value = self.initial.get('training_cycle')
            if isinstance(value, TrainingCycle):
                return value

        if value:
            try:
                return queryset.get(pk=value)
            except (TrainingCycle.DoesNotExist, ValueError, TypeError):
                return None
        return None

