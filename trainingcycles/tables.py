import django_tables2 as tables

from core.utils.tables import ActionsColumn, BaseDateColumn, BaseTable

from .models import TrainingCycle


class TrainingCycleTable(BaseTable):
    start_date = BaseDateColumn(verbose_name='开始日期')
    end_date = BaseDateColumn(verbose_name='结束日期')
    status = tables.Column(verbose_name='状态', accessor='get_status_display')
    actions = ActionsColumn(
        view_url='trainingcycles:detail',
        view_perm=None,
        verbose_name='操作',
    )

    class Meta(BaseTable.Meta):
        model = TrainingCycle
        fields = (
            'name',
            'project',
            'module_set',
            'status',
            'start_date',
            'end_date',
            'primary_competition_project',
            'reference_competition_project',
            'actions',
        )
        order_by = ('-start_date',)

