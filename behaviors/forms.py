from django import forms
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from core.constants import (
    CONDUCT_NATURE_CHOICES,
    CONDUCT_NATURE_PENALTY,
)
from core.permissions import get_users_with_explicit_permission
from core.uploads import CONDUCT_ATTACHMENT_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from .models import ConductItem, ConductRecord, get_conduct_severity_choices_with_multiplier

User = get_user_model()


class ConductRecordForm(StyledFormMixin, forms.ModelForm):
    nature = forms.ChoiceField(
        label='奖惩性质',
        choices=CONDUCT_NATURE_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'aria-label': 'nature-select',
            'hx-trigger': 'change',
            'hx-target': '#id_item',
            'hx-swap': 'innerHTML',
        }),
    )

    class Meta:
        model = ConductRecord
        fields = ['student', 'item', 'severity', 'occurred_date', 'reason', 'attachment']
        widgets = {
            'student': forms.Select(attrs={'aria-label': 'student-select'}),
            'item': forms.Select(attrs={
                'aria-label': 'item-select',
                'hx-trigger': 'change',
                'hx-target': '#id_severity',
                'hx-swap': 'innerHTML',
            }),
            'severity': forms.Select(attrs={'aria-label': 'severity-select'}),
            'occurred_date': forms.DateInput(attrs={'type': 'date', 'aria-label': 'date-input'}),
            'reason': forms.Textarea(attrs={
                'rows': 3,
                'aria-label': 'reason-input',
                'placeholder': '请描述具体原因',
            }),
            'attachment': forms.FileInput(attrs=CONDUCT_ATTACHMENT_UPLOAD_SPEC.widget_attrs(
                **{'aria-label': 'file-input'}
            )),
        }

    field_order = ['student', 'nature', 'item', 'severity', 'occurred_date', 'reason', 'attachment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 限定学生选择范围，使用 display_name 显示
        self.fields['student'].queryset = get_users_with_explicit_permission(
            "behaviors.be_conduct_subject",
            User.objects.filter(is_active=True),
        ).order_by('username')
        self.fields['student'].label_from_instance = lambda obj: obj.display_name

        # HTMX: 选择性质后动态更新事项选项
        self.fields['nature'].widget.attrs['hx-get'] = reverse('behaviors:item_choices')

        # HTMX: 选择事项后动态更新程度选项
        self.fields['item'].widget.attrs['hx-get'] = reverse('behaviors:severity_choices')

        # 修改严重程度字段标签
        self.fields['severity'].label = '程度'

        # 根据提交数据或实例恢复 nature / item / severity 的选项列表
        nature = None
        if self.data and self.data.get('item'):
            try:
                item = ConductItem.objects.select_related('category').get(
                    pk=self.data['item'],
                )
                nature = item.category.nature
            except (ConductItem.DoesNotExist, ValueError):
                pass
        elif self.instance.pk and self.instance.item_id:
            nature = self.instance.item.category.nature
        elif not self.data:
            # 新建表单：默认选择惩罚
            nature = CONDUCT_NATURE_PENALTY

        if nature:
            # 恢复 nature 字段选中值
            self.initial['nature'] = nature
            # 恢复 item 下拉：仅显示对应性质的事项
            self.fields['item'].queryset = ConductItem.objects.filter(
                is_active=True,
                category__nature=nature,
            ).select_related('category')
            # 恢复 severity 下拉（显示系数）
            self.fields['severity'].choices = get_conduct_severity_choices_with_multiplier(nature)
        else:
            # 初始状态：事项和程度均为占位提示
            self.fields['item'].queryset = ConductItem.objects.none()
            self.fields['severity'].choices = [('', '请先选择奖惩事项')]

        # 设置默认日期为今天
        if not self.instance.pk:
            today = timezone.localdate()
            self.fields['occurred_date'].initial = today.strftime('%Y-%m-%d')
            self.fields['occurred_date'].widget.attrs['value'] = today.strftime('%Y-%m-%d')
