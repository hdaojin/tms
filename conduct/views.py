from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin
from core.constants import GROUP_COMPETITOR, GROUP_COACH
from .models import ConductType, ConductRecord, ConductSummary
from .forms import (
    ConductTypeForm,
    ConductRecordForm,
    ConductRecordReviewForm,
    ConductRecordFilterForm
)
from .tables import ConductTypeTable, ConductRecordTable, ConductSummaryTable


User = get_user_model()


# ==================== 奖惩类型视图 ====================

class ConductTypeListView(
    TitleMixin,
    PermissionRequiredMixin,
    SingleTableView
):
    """奖惩类型列表"""
    model = ConductType
    table_class = ConductTypeTable
    template_name = 'conduct/type_list.html'
    title = '奖惩类型管理'
    title_icon = 'icon-[tabler--category]'
    permission_required = 'conduct.manage_conduct_types'
    paginate_by = 20


class ConductTypeDetailView(
    TitleMixin,
    PermissionRequiredMixin,
    DetailView
):
    """奖惩类型详情"""
    model = ConductType
    template_name = 'conduct/type_detail.html'
    context_object_name = 'conduct_type'
    title = '{name}'
    title_icon = 'icon-[tabler--info-circle]'
    permission_required = 'conduct.view_conducttype'


class ConductTypeCreateView(
    TitleMixin,
    PermissionRequiredMixin,
    CreateView
):
    """创建奖惩类型"""
    model = ConductType
    form_class = ConductTypeForm
    template_name = 'conduct/type_form.html'
    title = '创建奖惩类型'
    title_icon = 'icon-[tabler--plus]'
    permission_required = 'conduct.manage_conduct_types'
    success_url = reverse_lazy('conduct:type_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, f'奖惩类型 "{form.instance.name}" 创建成功！')
        return super().form_valid(form)


class ConductTypeUpdateView(
    TitleMixin,
    PermissionRequiredMixin,
    UpdateView
):
    """更新奖惩类型"""
    model = ConductType
    form_class = ConductTypeForm
    template_name = 'conduct/type_form.html'
    title = '编辑奖惩类型'
    title_icon = 'icon-[tabler--edit]'
    permission_required = 'conduct.manage_conduct_types'
    success_url = reverse_lazy('conduct:type_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'奖惩类型 "{form.instance.name}" 更新成功！')
        return super().form_valid(form)


class ConductTypeDeleteView(
    TitleMixin,
    PermissionRequiredMixin,
    DeleteView
):
    """删除奖惩类型"""
    model = ConductType
    template_name = 'conduct/type_confirm_delete.html'
    title = '删除奖惩类型'
    title_icon = 'icon-[tabler--trash]'
    permission_required = 'conduct.manage_conduct_types'
    success_url = reverse_lazy('conduct:type_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'奖惩类型 "{self.object.name}" 已删除！')
        return super().form_valid(form)


# ==================== 奖惩记录视图 ====================

class ConductRecordListView(
    TitleMixin,
    PermissionRequiredMixin,
    SingleTableView
):
    """奖惩记录列表"""
    model = ConductRecord
    table_class = ConductRecordTable
    template_name = 'conduct/record_list.html'
    title = '奖惩记录'
    title_icon = 'icon-[tabler--file-text]'
    permission_required = 'conduct.view_conductrecord'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'student',
            'record_type',
            'recorded_by',
            'reviewed_by'
        )
        
        # 选手只能看自己的记录
        user = self.request.user
        if not (user.is_superuser or 
                user.has_perm('conduct.view_all_conduct_records') or
                user.groups.filter(name=GROUP_COACH).exists()):
            queryset = queryset.filter(student=user)
        
        # 应用筛选
        form = self.get_filter_form()
        if form.is_valid():
            student = form.cleaned_data.get('student')
            category = form.cleaned_data.get('category')
            status = form.cleaned_data.get('status')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            
            if student:
                queryset = queryset.filter(student=student)
            if category:
                queryset = queryset.filter(record_type__category=category)
            if status:
                queryset = queryset.filter(status=status)
            if date_from:
                queryset = queryset.filter(occurred_date__gte=date_from)
            if date_to:
                queryset = queryset.filter(occurred_date__lte=date_to)
        
        return queryset
    
    def get_filter_form(self):
        """获取筛选表单"""
        user = self.request.user
        show_all = (user.is_superuser or 
                   user.has_perm('conduct.view_all_conduct_records') or
                   user.groups.filter(name=GROUP_COACH).exists())
        
        return ConductRecordFilterForm(
            self.request.GET,
            show_all_students=show_all
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.get_filter_form()
        return context


class ConductRecordDetailView(
    TitleMixin,
    PermissionRequiredMixin,
    DetailView
):
    """奖惩记录详情"""
    model = ConductRecord
    template_name = 'conduct/record_detail.html'
    context_object_name = 'record'
    title = '{student} - {record_type}'
    title_icon = 'icon-[tabler--info-circle]'
    permission_required = 'conduct.view_conductrecord'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # 选手只能看自己的记录
        if not (user.is_superuser or 
                user.has_perm('conduct.view_all_conduct_records') or
                user.groups.filter(name=GROUP_COACH).exists()):
            queryset = queryset.filter(student=user)
        
        return queryset


class ConductRecordCreateView(
    TitleMixin,
    PermissionRequiredMixin,
    CreateView
):
    """创建奖惩记录"""
    model = ConductRecord
    form_class = ConductRecordForm
    template_name = 'conduct/record_form.html'
    title = '录入奖惩记录'
    title_icon = 'icon-[tabler--plus]'
    permission_required = 'conduct.add_conduct_record'
    success_url = reverse_lazy('conduct:record_list')
    
    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        form.instance.status = 'PENDING'  # 默认待审核
        messages.success(
            self.request,
            f'已为 {form.instance.student} 录入奖惩记录，等待审核！'
        )
        return super().form_valid(form)


class ConductRecordUpdateView(
    TitleMixin,
    PermissionRequiredMixin,
    UpdateView
):
    """更新奖惩记录"""
    model = ConductRecord
    form_class = ConductRecordForm
    template_name = 'conduct/record_form.html'
    title = '编辑奖惩记录'
    title_icon = 'icon-[tabler--edit]'
    permission_required = 'conduct.change_conductrecord'
    success_url = reverse_lazy('conduct:record_list')
    
    def get_queryset(self):
        """只能编辑待审核的记录"""
        queryset = super().get_queryset()
        return queryset.filter(status='PENDING')
    
    def form_valid(self, form):
        messages.success(self.request, '奖惩记录更新成功！')
        return super().form_valid(form)


class ConductRecordDeleteView(
    TitleMixin,
    PermissionRequiredMixin,
    DeleteView
):
    """删除奖惩记录"""
    model = ConductRecord
    template_name = 'conduct/record_confirm_delete.html'
    title = '删除奖惩记录'
    title_icon = 'icon-[tabler--trash]'
    permission_required = 'conduct.delete_conductrecord'
    success_url = reverse_lazy('conduct:record_list')
    
    def form_valid(self, form):
        messages.success(self.request, '奖惩记录已删除！')
        return super().form_valid(form)


class ConductRecordReviewView(
    TitleMixin,
    PermissionRequiredMixin,
    UpdateView
):
    """审核奖惩记录"""
    model = ConductRecord
    form_class = ConductRecordReviewForm
    template_name = 'conduct/record_review.html'
    title = '审核奖惩记录'
    title_icon = 'icon-[tabler--check]'
    permission_required = 'conduct.review_conduct_record'
    success_url = reverse_lazy('conduct:record_list')
    
    def get_queryset(self):
        """只能审核待审核的记录"""
        return super().get_queryset().filter(status='PENDING')
    
    def form_valid(self, form):
        form.instance.reviewed_by = self.request.user
        form.instance.reviewed_at = timezone.now()
        
        status_text = '通过' if form.instance.status == 'APPROVED' else '驳回'
        messages.success(
            self.request,
            f'已{status_text}该奖惩记录！'
        )
        return super().form_valid(form)


# ==================== 奖惩汇总视图 ====================

class ConductSummaryListView(
    TitleMixin,
    PermissionRequiredMixin,
    SingleTableView
):
    """奖惩汇总列表（排行榜）"""
    model = ConductSummary
    table_class = ConductSummaryTable
    template_name = 'conduct/summary_list.html'
    title = '奖惩排行榜'
    title_icon = 'icon-[tabler--trophy]'
    permission_required = 'conduct.view_conductsummary'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('student')
        
        # 选手只能看自己的汇总
        user = self.request.user
        if not (user.is_superuser or 
                user.has_perm('conduct.view_all_conduct_records') or
                user.groups.filter(name=GROUP_COACH).exists()):
            queryset = queryset.filter(student=user)
        
        return queryset.order_by('-total_score', 'student__first_name')


class StudentConductDetailView(
    TitleMixin,
    PermissionRequiredMixin,
    DetailView
):
    """学生奖惩详情（个人档案）"""
    model = User
    template_name = 'conduct/student_detail.html'
    context_object_name = 'student'
    pk_url_kwarg = 'student_id'
    title = '{first_name}的奖惩档案'
    title_icon = 'icon-[tabler--user]'
    permission_required = 'conduct.view_conductrecord'
    
    def get_queryset(self):
        queryset = User.objects.filter(groups__name=GROUP_COMPETITOR)
        
        # 选手只能看自己
        user = self.request.user
        if not (user.is_superuser or 
                user.has_perm('conduct.view_all_conduct_records') or
                user.groups.filter(name=GROUP_COACH).exists()):
            queryset = queryset.filter(id=user.id)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object
        
        # 获取或创建汇总信息
        summary, created = ConductSummary.objects.get_or_create(
            student=student
        )
        if created:
            summary.update_summary()
        
        context['summary'] = summary
        
        # 获取所有记录
        context['records'] = student.conduct_records.select_related(
            'record_type',
            'recorded_by',
            'reviewed_by'
        ).order_by('-occurred_date')
        
        # 统计信息
        approved_records = student.conduct_records.filter(status='APPROVED')
        context['stats'] = {
            'total_records': student.conduct_records.count(),
            'pending_count': student.conduct_records.filter(status='PENDING').count(),
            'approved_count': approved_records.count(),
            'rejected_count': student.conduct_records.filter(status='REJECTED').count(),
        }
        
        return context


class MyConductView(TitleMixin, PermissionRequiredMixin, DetailView):
    """我的奖惩（选手专用）"""
    model = User
    template_name = 'conduct/my_conduct.html'
    context_object_name = 'student'
    title = '我的奖惩'
    title_icon = 'icon-[tabler--user-check]'
    permission_required = 'conduct.view_conductrecord'
    
    def get_object(self):
        return self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # 获取或创建汇总信息
        summary, created = ConductSummary.objects.get_or_create(
            student=user
        )
        if created:
            summary.update_summary()
        
        context['summary'] = summary
        
        # 获取记录
        context['records'] = user.conduct_records.select_related(
            'record_type',
            'recorded_by',
            'reviewed_by'
        ).order_by('-occurred_date')[:20]  # 最近20条
        
        return context
