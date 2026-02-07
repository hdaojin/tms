import django_tables2 as tables
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from core.utils.tables import BaseTable, BaseDateColumn, ActionsColumn
from .models import ConductRecord, ConductSummary


class ConductRecordTable(BaseTable):
    """奖惩记录表格"""
    
    student = tables.Column(
        verbose_name='学生',
        accessor='student.display_name',
        order_by=('student__last_name', 'student__first_name', 'student__username')
    )
    item = tables.Column(verbose_name='奖惩事项')
    occurred_date = BaseDateColumn(verbose_name='发生日期')
    score = tables.Column(verbose_name='得分')
    status = tables.Column(verbose_name='状态')
    recorded_by = tables.Column(
        verbose_name='记录人',
        accessor='recorded_by.display_name'
    )
    recorded_at = BaseDateColumn(verbose_name='记录时间')
    
    actions = ActionsColumn(
        view_url='conduct:record_detail',
        edit_url='conduct:record_update',
        delete_url='conduct:record_delete',
        edit_perm='conduct.change_conductrecord',
        delete_perm='conduct.delete_conductrecord',
    )
    
    class Meta(BaseTable.Meta):
        model = ConductRecord
        fields = [
            'student',
            'item',
            'occurred_date',
            'score',
            'status',
            'recorded_by',
            'recorded_at'
        ]
    
    def render_student(self, record):
        """显示学生姓名"""
        return record.student.display_name
    
    def render_score(self, value):
        """格式化得分显示"""
        color_class = 'text-success' if value > 0 else 'text-error'
        return format_html(
            '<span class="{}">{}</span>',
            color_class,
            f'{float(value):+.1f}'
        )
    
    def render_status(self, record):
        """格式化状态显示"""
        status_map = {
            'PENDING': ('badge-warning', '待审核'),
            'APPROVED': ('badge-success', '已通过'),
            'REJECTED': ('badge-error', '已驳回'),
        }
        badge_class, label = status_map.get(record.status, ('badge-ghost', '未知'))
        return format_html(
            '<span class="badge {}">{}</span>',
            badge_class,
            label
        )
    
    def render_recorded_by(self, record):
        """显示记录人姓名"""
        if record.recorded_by:
            return record.recorded_by.display_name
        return '-'


class ConductSummaryTable(BaseTable):
    """奖惩汇总表格"""
    
    rank = tables.Column(
        verbose_name='排名',
        orderable=False,
        empty_values=()
    )
    student = tables.Column(
        verbose_name='学生',
        accessor='student__first_name',
        order_by=('student__first_name', 'student__username')
    )
    total_score = tables.Column(verbose_name='总分')
    reward_count = tables.Column(verbose_name='奖励次数')
    penalty_count = tables.Column(verbose_name='惩罚次数')
    last_updated = BaseDateColumn(verbose_name='更新时间')
    
    def render_actions(self, record):
        """自定义渲染操作列，传递student.id"""
        from django.urls import reverse
        student_id = record.student.id
        url = reverse('conduct:student_detail', args=[student_id])
        return format_html(
            '<a class="btn btn-soft btn-primary btn-xs" href="{}">查看</a>',
            url
        )
    
    actions = tables.Column(
        verbose_name='操作',
        orderable=False,
        empty_values=()
    )
    
    class Meta(BaseTable.Meta):
        model = ConductSummary
        fields = [
            'rank',
            'student',
            'total_score',
            'reward_count',
            'penalty_count',
            'last_updated'
        ]
    
    def render_rank(self, record):
        """渲染排名"""
        # 通过table的data获取当前记录的索引
        try:
            index = list(self.data.data).index(record) + 1
            if index <= 3:
                medal_icons = {
                    1: '🥇',
                    2: '🥈',
                    3: '🥉'
                }
                return mark_safe(
                    f'<span class="text-xl">{medal_icons[index]}</span>'
                )
            return index
        except (ValueError, AttributeError):
            return '-'
    
    def render_student(self, record):
        """显示学生姓名"""
        return record.student.display_name
    
    def render_total_score(self, value):
        """格式化总分显示"""
        if value > 0:
            color_class = 'text-success font-bold'
        elif value < 0:
            color_class = 'text-error font-bold'
        else:
            color_class = 'text-base-content'
        
        return format_html(
            '<span class="{}">{}</span>',
            color_class,
            f'{float(value):+.1f}'
        )
