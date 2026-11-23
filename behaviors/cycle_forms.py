from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator
from django.utils import timezone

from accounts.services.users import annotate_identity_labels, get_user_full_info, require_distinguishable_users
from core.uploads import CONDUCT_ATTACHMENT_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from .cycle_services import active_policy
from .models import (
    ConductCategory, ConductCycleAssignment, ConductItem, ConductNature, ConductPolicy,
    ConductPolicyItem, ConductPolicyRule, ConductSeverity, ConductSeverityRule, get_conduct_severity_rules,
    get_default_conduct_severity,
)


DATE = forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})


class PolicyForm(StyledFormMixin, forms.ModelForm):
    revision = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = ConductPolicy
        fields = ['title', 'issuer', 'body', 'change_note', 'effective_date']
        widgets = {'effective_date': DATE}


class PolicyItemForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ConductPolicyItem
        fields = ['item', 'base_score']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = ConductItem.objects.filter(
            is_active=True, category__is_active=True, category__nature__in=ConductNature.values,
        ).select_related('category')
        if self.instance.pk:
            self.fields['item'].queryset = ConductItem.objects.filter(pk=self.instance.item_id)
            self.fields['item'].disabled = True
        self.fields['base_score'].required = bool(self.instance.pk)
        self.fields['base_score'].help_text = '新增时留空将采用共享事项的基准分。'

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('item') and cleaned.get('base_score') is None:
            cleaned['base_score'] = cleaned['item'].default_score
        return cleaned


class RuleForm(StyledFormMixin, forms.ModelForm):
    template = forms.ModelChoiceField(
        label='通用程度与倍率', queryset=ConductSeverityRule.objects.none(), required=False,
        empty_label='自定义分档', help_text='选用通用档位时自动填入该档位的名称和倍率。',
    )

    class Meta:
        model = ConductPolicyRule
        fields = ['section', 'template', 'condition', 'multiplier', 'unit', 'order']

    def __init__(self, *args, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.policy_item = group
        nature = group.item.category.nature
        self.fields['template'].queryset = get_conduct_severity_rules(nature)
        if not self.instance.pk:
            self.initial.setdefault('template', get_default_conduct_severity(nature))
        self.fields['condition'].required = False
        self.fields['multiplier'].required = False

    def clean(self):
        cleaned = super().clean()
        if template := cleaned.get('template'):
            cleaned['condition'] = template.label
            cleaned['multiplier'] = template.multiplier
            self.instance.severity = template.severity
        else:
            if (self.instance.condition, self.instance.multiplier) != (cleaned.get('condition'), cleaned.get('multiplier')):
                self.instance.severity = None
            if not cleaned.get('condition'):
                self.add_error('condition', '请输入分档名称。')
            if cleaned.get('multiplier') is None and 'multiplier' not in self.errors:
                self.add_error('multiplier', '请输入倍率。')
        return cleaned


class AssignmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ConductCycleAssignment
        fields = ['user', 'can_enter', 'can_review', 'can_write', 'can_publish']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = annotate_identity_labels(
            get_user_model().objects.filter(is_active=True).order_by('last_name', 'first_name', 'pk')
        )
        self.fields['user'].label_from_instance = get_user_full_info
        self.fields['user'].disabled = bool(self.instance.pk)

    def clean_user(self):
        user = self.cleaned_data['user']
        if not self.instance.pk:
            require_distinguishable_users(self.fields['user'].queryset, [user.pk])
        return user


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ConductCategory
        fields = ['nature', 'code', 'name', 'description', 'order', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('code', 'nature'):
            self.fields[name].disabled = bool(self.instance.pk)
        if self.instance.pk and self.instance.nature not in ConductNature:
            self.fields.pop('nature')


class ItemForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ConductItem
        fields = ['category', 'code', 'name', 'default_score', 'description', 'is_active']

    def __init__(self, *args, category, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ConductCategory.objects.filter(pk=category.pk)
        self.fields['category'].initial = category.pk
        self.fields['category'].disabled = True
        self.fields['code'].disabled = bool(self.instance.pk)


class SeverityForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ConductSeverity
        fields = ['code', 'name', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].disabled = bool(self.instance.pk)


class SeverityRuleForm(StyledFormMixin, forms.ModelForm):
    set_default = forms.BooleanField(label='设为该性质的默认档', required=False)

    class Meta:
        model = ConductSeverityRule
        fields = ['nature', 'severity', 'label', 'multiplier', 'order', 'is_active', 'set_default']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('nature', 'severity'):
            self.fields[name].disabled = bool(self.instance.pk)
        self.initial.setdefault('set_default', self.instance.is_default)

    def clean(self):
        cleaned = super().clean()
        self.instance.is_default = cleaned.get('set_default', False)
        severity = cleaned.get('severity')
        if self.instance.is_default and severity and not (severity.is_active and cleaned.get('is_active')):
            self.add_error('set_default', '默认档及其关联程度都必须启用。')
        return cleaned


def eligible_students(cycle):
    return annotate_identity_labels(
        get_user_model().objects.filter(
            is_active=True, training_cycle_memberships__training_cycle=cycle,
            training_cycle_memberships__role='competitor',
        ).order_by('last_name', 'first_name', 'pk')
    )


class EntryDateForm(StyledFormMixin, forms.Form):
    occurred_date = forms.DateField(label='发生日期', widget=DATE, initial=timezone.localdate)

    def clean_occurred_date(self):
        date = self.cleaned_data['occurred_date']
        if date > timezone.localdate():
            raise ValidationError('发生日期不能晚于今天。')
        return date


class EntryForm(EntryDateForm):
    students = forms.ModelMultipleChoiceField(label='学员', queryset=get_user_model().objects.none())
    rule = forms.ModelChoiceField(label='程度或分档', queryset=ConductPolicyRule.objects.none())
    quantity = forms.IntegerField(label='计分数量', min_value=1, max_value=10000, initial=1)
    reason = forms.CharField(label='具体事实', widget=forms.Textarea(attrs={'rows': 4}))
    attachment = forms.FileField(
        label='附件', required=False, validators=CONDUCT_ATTACHMENT_UPLOAD_SPEC.validators(),
        widget=forms.FileInput(attrs=CONDUCT_ATTACHMENT_UPLOAD_SPEC.widget_attrs()),
    )
    confirmation = forms.CharField(required=False, widget=forms.HiddenInput)
    revision = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, cycle, date, record=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.record = record
        policy = active_policy(cycle, date)
        rules = policy.rules if policy else ConductPolicyRule.objects.none()
        if record:
            rules = record.rule.policy_item.policy.rules
            self.fields['occurred_date'].disabled = True
            self.fields['students'].disabled = True
            students = get_user_model().objects.filter(pk=record.student_id)
        else:
            students = eligible_students(cycle)
        self.fields['rule'].queryset = rules.select_related('policy_item__item', 'policy_item__policy', 'severity')
        self.fields['students'].queryset = students
        self.fields['students'].label_from_instance = get_user_full_info

    def clean_students(self):
        students = list(self.cleaned_data['students'])
        if not self.record:
            require_distinguishable_users(self.fields['students'].queryset, [student.pk for student in students])
        return students

    def clean(self):
        data = super().clean()
        rule, quantity = data.get('rule'), data.get('quantity')
        if rule and quantity:
            if not rule.unit and quantity != 1:
                self.add_error('quantity', '固定分值规则的数量必须为 1。')
            points = (rule.points * quantity).quantize(Decimal('0.0001'))
            try:
                DecimalValidator(16, 4)(points)
            except ValidationError:
                self.add_error('quantity', '本次积分超出可记录范围，请核对数量。')
            data['points'] = points
        return data
