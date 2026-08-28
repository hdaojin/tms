from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.permissions import get_users_with_explicit_permission
from core.uploads import CONDUCT_ATTACHMENT_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from .models import (
    ConductItem,
    ConductNature,
    ConductRecord,
    ConductSeverity,
    get_conduct_severity_rules,
)

User = get_user_model()


def configure_severity_field(field, nature, *, current_severity_id=None):
    field.to_field_name = 'code'
    if not nature:
        field.queryset = ConductSeverity.objects.none()
        return None

    rules = list(
        get_conduct_severity_rules(
            nature,
            current_severity_id=current_severity_id,
        )
    )
    rule_by_severity_id = {rule.severity_id: rule for rule in rules}
    field.queryset = (
        ConductSeverity.objects.filter(pk__in=rule_by_severity_id)
        .filter(rules__nature=nature)
        .filter(Q(is_active=True) | Q(pk=current_severity_id))
        .order_by('rules__order', 'code')
        .distinct()
    )
    field.label_from_instance = lambda severity: (
        f'{rule_by_severity_id[severity.pk].label}'
        f'（×{rule_by_severity_id[severity.pk].multiplier:.2f}）'
    )
    default_rule = next(
        (rule for rule in rules if rule.is_default and rule.severity.is_active),
        None,
    )
    return default_rule.severity.code if default_rule is not None else None


class ConductRecordForm(StyledFormMixin, forms.ModelForm):
    nature = forms.ChoiceField(
        label='奖惩性质',
        choices=ConductNature.choices,
        required=True,
        widget=forms.Select(attrs={
            'aria-label': 'nature-select',
            'hx-trigger': 'change',
            'hx-target': '#id_item',
            'hx-swap': 'innerHTML',
        }),
    )
    severity = forms.ModelChoiceField(
        label='程度',
        queryset=ConductSeverity.objects.none(),
        to_field_name='code',
        empty_label='请选择程度',
        widget=forms.Select(attrs={'aria-label': 'severity-select'}),
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

        # 根据提交数据或实例恢复 nature / item / severity 的选项列表
        nature = None
        selected_item = None
        if self.data and self.data.get('item'):
            try:
                selected_item = ConductItem.objects.select_related('category').get(
                    pk=self.data['item'],
                    is_active=True,
                    category__is_active=True,
                    category__nature__in=ConductNature.values,
                )
                nature = selected_item.category.nature
            except (ConductItem.DoesNotExist, ValueError):
                pass
        elif self.instance.pk and self.instance.item_id:
            selected_item = self.instance.item
            nature = self.instance.item.category.nature
        elif not self.data:
            # 新建表单：默认选择惩罚
            nature = ConductNature.PENALTY

        if nature:
            # 恢复 nature 字段选中值
            self.initial['nature'] = nature
            # 恢复 item 下拉：仅显示对应性质的事项
            self.fields['item'].queryset = ConductItem.objects.filter(
                is_active=True,
                category__is_active=True,
                category__nature=nature,
            ).select_related('category')
        else:
            self.fields['item'].queryset = ConductItem.objects.none()

        if selected_item is not None:
            current_severity_id = self.instance.severity_id if self.instance.pk else None
            default_code = configure_severity_field(
                self.fields['severity'],
                selected_item.category.nature,
                current_severity_id=current_severity_id,
            )
            if not self.is_bound and not self.instance.pk and default_code:
                self.fields['severity'].initial = default_code
        else:
            self.fields['severity'].queryset = ConductSeverity.objects.none()
            self.fields['severity'].empty_label = '请先选择奖惩事项'

        # 设置默认日期为今天
        if not self.instance.pk:
            today = timezone.localdate()
            self.fields['occurred_date'].initial = today.strftime('%Y-%m-%d')
            self.fields['occurred_date'].widget.attrs['value'] = today.strftime('%Y-%m-%d')
