import django_tables2 as tables

from core.utils.tables import BaseTable, BaseDateColumn, BaseDateTimeColumn
from .models import ConductRecord, ConductSummary


class ConductRecordTable(BaseTable):
    student = tables.Column(
        verbose_name="学生",
        accessor="student.display_name",
    )
    item = tables.Column(verbose_name="奖惩事项", accessor="item.name")
    reason = tables.Column(verbose_name="具体原因/描述")
    severity_label = tables.Column(verbose_name="程度", orderable=False)
    occurred_date = BaseDateColumn(verbose_name="发生日期")
    score = tables.Column(verbose_name="分值", orderable=False)
    status = tables.Column(verbose_name="状态")
    recorded_at = BaseDateTimeColumn(verbose_name="记录时间")

    def render_score(self, record):
        score = record.score
        return f'{score:+.1f}'

    def render_status(self, record):
        return record.get_status_display()

    class Meta(BaseTable.Meta):
        model = ConductRecord
        fields = (
            "student",
            "item",
            "reason",
            "severity_label",
            "occurred_date",
            "score",
            "status",
            "recorded_at",
        )
        order_by = ("-occurred_date",)


class ConductSummaryTable(BaseTable):
    student = tables.Column(
        verbose_name="学生",
        accessor="student.display_name",
    )
    total_score = tables.Column(verbose_name="总分")
    reward_count = tables.Column(verbose_name="奖励次数")
    penalty_count = tables.Column(verbose_name="惩罚次数")
    last_updated = BaseDateTimeColumn(verbose_name="最后更新")

    def render_total_score(self, value):
        return f'{value:+.1f}'

    class Meta(BaseTable.Meta):
        model = ConductSummary
        fields = (
            "student",
            "total_score",
            "reward_count",
            "penalty_count",
            "last_updated",
        )
        order_by = ("-total_score",)
