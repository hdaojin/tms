import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html

from core.tables import ActionsColumn, BaseDateColumn, BaseTable

from .models import ConductCategory, ConductItem, ConductRecord, ConductSeverity, ConductSeverityRule, format_conduct_score


class ConductRecordTable(BaseTable):
    occurred_date = BaseDateColumn(verbose_name='发生日期')
    cycle = tables.Column(verbose_name='训练周期', empty_values=())
    student = tables.Column(verbose_name='学员', accessor='student__display_name', order_by=('student__last_name', 'student__first_name'))
    nature = tables.Column(verbose_name='奖惩性质', accessor='nature_label', order_by='frozen_nature')
    item_label = tables.Column(verbose_name='奖惩事项', linkify=('behaviors:record_detail', [tables.A('pk')]))
    severity_label = tables.Column(verbose_name='程度或分档')
    frozen_points = tables.Column(verbose_name='积分')
    status = tables.Column(verbose_name='状态')

    class Meta(BaseTable.Meta):
        model = ConductRecord
        fields = ('occurred_date', 'cycle', 'student', 'nature', 'item_label', 'severity_label', 'frozen_points', 'status')

    def render_cycle(self, value):
        return value or '未关联周期'

    def render_frozen_points(self, value):
        return format_conduct_score(value)


class ConductSummaryTable(BaseTable):
    cycle = tables.Column(verbose_name='训练周期', accessor='cycle__name', empty_values=())
    student = tables.Column(verbose_name='学员', accessor='student_id', order_by=('student__last_name', 'student__first_name'))
    competition = tables.Column(verbose_name='竞赛奖励', empty_values=())
    management = tables.Column(verbose_name='日常管理', empty_values=())
    learning = tables.Column(verbose_name='日常学习', empty_values=())
    total_score = tables.Column(verbose_name='合计')
    reward_count = tables.Column(verbose_name='奖励次数')
    penalty_count = tables.Column(verbose_name='惩罚次数')

    class Meta(BaseTable.Meta):
        pass

    def render_cycle(self, value):
        return value or '未关联周期'

    def render_student(self, record):
        return (record['student__last_name'] + record['student__first_name']).strip() or '未填写姓名'

    def render_competition(self, value, record):
        return format_conduct_score(value or 0) if record['cycle_id'] else '—'

    render_management = render_competition
    render_learning = render_competition

    def render_total_score(self, value):
        return format_conduct_score(value)


class CatalogCategoryTable(BaseTable):
    name = tables.Column(verbose_name='分类名称', linkify=('behaviors:catalog_items', [tables.A('pk')]))
    nature = tables.Column(verbose_name='奖惩性质')
    is_active = tables.Column(verbose_name='状态')
    actions = ActionsColumn(view_url='behaviors:category_detail', edit_url='behaviors:category_edit', view_label='分类详情')

    class Meta(BaseTable.Meta):
        model = ConductCategory
        fields = ('name', 'nature', 'code', 'order', 'is_active', 'actions')

    def render_nature(self, record):
        return record.nature_label

    def render_is_active(self, value):
        return '启用' if value else '停用'


class CatalogItemTable(BaseTable):
    name = tables.Column(verbose_name='事项名称', linkify=('behaviors:item_detail', [tables.A('category_id'), tables.A('pk')]))
    is_active = tables.Column(verbose_name='状态')
    actions = tables.Column(verbose_name='操作', empty_values=(), orderable=False)

    class Meta(BaseTable.Meta):
        model = ConductItem
        fields = ('name', 'code', 'default_score', 'is_active', 'actions')

    def render_is_active(self, value):
        return '启用' if value else '停用'

    def render_actions(self, record):
        return format_html(
            '<a class="btn btn-ghost btn-sm" href="{}">编辑</a>',
            reverse('behaviors:item_edit', args=[record.category_id, record.pk]),
        )


class SeverityRateTable(BaseTable):
    label = tables.Column(linkify=('behaviors:rate_edit', [tables.A('pk')]))
    severity = tables.Column(linkify=('behaviors:severity_edit', [tables.A('severity_id')]))
    active = tables.Column(verbose_name='状态', accessor='is_active', orderable=False)
    is_default = tables.Column(verbose_name='默认档')

    class Meta(BaseTable.Meta):
        model = ConductSeverityRule
        fields = ('nature', 'severity', 'label', 'multiplier', 'order', 'active', 'is_default')

    def render_active(self, value, record):
        return '启用' if value and record.severity.is_active else '停用'

    def render_is_default(self, value):
        return '默认' if value else '—'


class SeverityTable(BaseTable):
    name = tables.Column(linkify=('behaviors:severity_edit', [tables.A('pk')]))
    is_active = tables.Column(verbose_name='状态')

    class Meta(BaseTable.Meta):
        model = ConductSeverity
        fields = ('name', 'code', 'description', 'is_active')

    def render_is_active(self, value):
        return '启用' if value else '停用'
