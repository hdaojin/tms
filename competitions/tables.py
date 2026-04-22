import django_tables2 as tables

from core.utils.tables import ActionsColumn, BaseDateColumn, BaseTable

from .models import Competition


class CompetitionTable(BaseTable):
    competition_type = tables.Column(verbose_name='赛事类型', accessor='competition_type.name')
    level = tables.Column(verbose_name='级别', accessor='competition_type.get_level_display', orderable=False)
    start_date = BaseDateColumn(verbose_name='开始日期')
    competition_project_total = tables.Column(verbose_name='赛项数', empty_values=(), orderable=False)
    actions = ActionsColumn(
        view_url='competitions:competition_detail',
        view_perm=None,
        verbose_name='操作',
    )

    class Meta(BaseTable.Meta):
        model = Competition
        fields = ('name', 'code', 'competition_type', 'level', 'start_date', 'location', 'competition_project_total', 'actions')
        order_by = ('-start_date', 'name')

    def render_competition_project_total(self, record):
        return getattr(record, 'competition_project_total', 0)