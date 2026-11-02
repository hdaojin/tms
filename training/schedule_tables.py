import django_tables2 as tables
from core.tables import BaseTable, BaseDateColumn


class ScheduleTable(BaseTable):
    date = BaseDateColumn(accessor="day__date", verbose_name="日期")
    period = tables.Column(verbose_name="时段", orderable=False)
    kind = tables.Column(verbose_name="类型")
    domains = tables.TemplateColumn(
        template_name="training/schedule_domains.html", verbose_name="领域", orderable=False
    )
    coaches = tables.TemplateColumn(
        template_name="training/schedule_coaches.html", verbose_name="负责教练", orderable=False
    )
    duty = tables.TemplateColumn(
        template_name="training/schedule_duty.html", verbose_name="值班教练 / 日备注", orderable=False
    )
    tasks = tables.TemplateColumn(
        template_name="training/schedule_tasks.html", verbose_name="训练任务", orderable=False
    )
    actions = tables.TemplateColumn(
        template_name="training/schedule_actions.html", verbose_name="操作", orderable=False
    )

    class Meta(BaseTable.Meta):
        empty_text = "没有符合条件的排班条目。"
        row_attrs = {"id": lambda record: f"schedule-slot-{record.pk}"}

    def render_period(self, record):
        return record.get_period_display()

    def render_kind(self, record):
        return record.get_kind_display()
