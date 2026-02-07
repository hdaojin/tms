from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from core.utils.forms import StyledFormMixin
from core.constants import GROUP_COMPETITOR
from .models import ConductItem, ConductRecord


User = get_user_model()


class StudentChoiceField(forms.ModelChoiceField):
    """自定义学生选择字段，显示学生的 display_name（姓名） 而不是用户名"""
    
    def label_from_instance(self, obj):
        return obj.display_name


class ConductRecordForm(StyledFormMixin, forms.ModelForm):
    """奖惩记录表单"""
    
    # 使用自定义的学生选择字段，显示 display_name
    student = StudentChoiceField(
        queryset=User.objects.none(),
        label='学生',
        required=True
    )
    
    class Meta:
        model = ConductRecord
        fields = [
            'student',
            'item',
            'occurred_date',
            'reason',
            'attachment'
        ]
        widgets = {
            'occurred_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 只显示选手组的学生，按姓名和用户名排序
        try:
            competitor_group = Group.objects.get(name=GROUP_COMPETITOR)
            self.fields['student'].queryset = User.objects.filter(
                groups=competitor_group,
                is_active=True
            ).order_by('last_name', 'first_name', 'username')
        except Group.DoesNotExist:
            self.fields['student'].queryset = User.objects.none()
        
        # 只显启用的奖惩事项，按分类和名称排序
        self.fields['item'].queryset = ConductItem.objects.filter(
            is_active=True
        ).select_related('category').order_by(
            'category__nature',
            'category__order',
            'name'
        )


class ConductRecordReviewForm(StyledFormMixin, forms.ModelForm):
    """奖惩记录审核表单"""
    
    class Meta:
        model = ConductRecord
        fields = ['status', 'review_note']
        widgets = {
            'review_note': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 只允许选择通过或驳回
        self.fields['status'].choices = [
            ('APPROVED', '通过'),
            ('REJECTED', '驳回'),
        ]
        self.fields['review_note'].required = True


class ConductRecordFilterForm(forms.Form):
    """奖惩记录筛选表单"""
    
    STATUS_CHOICES = [
        ('', '全部状态'),
        ('PENDING', '待审核'),
        ('APPROVED', '已通过'),
        ('REJECTED', '已驳回'),
    ]
    
    CATEGORY_CHOICES = [
        ('', '全部类型'),
        ('REWARD', '奖励'),
        ('PENALTY', '惩罚'),
    ]
    
    student = StudentChoiceField(
        queryset=User.objects.none(),
        required=False,
        label='学生',
        empty_label='全部学生'
    )
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        required=False,
        label='类型'
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label='状态'
    )
    date_from = forms.DateField(
        required=False,
        label='开始日期',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        label='结束日期',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    def __init__(self, *args, **kwargs):
        show_all_students = kwargs.pop('show_all_students', False)
        super().__init__(*args, **kwargs)
        
        if show_all_students:
            # 教练/管理员看到所有选手
            try:
                competitor_group = Group.objects.get(name=GROUP_COMPETITOR)
                self.fields['student'].queryset = User.objects.filter(
                    groups=competitor_group,
                    is_active=True
                ).order_by('last_name', 'first_name', 'username')
            except Group.DoesNotExist:
                self.fields['student'].queryset = User.objects.none()
        else:
            # 选手只能筛选自己
            self.fields.pop('student', None)
