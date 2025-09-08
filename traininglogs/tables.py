# traininglogs/tables.py
import django_tables2 as tables
from common.tables import BaseTable, ActionsColumn
from .models import TrainingLog


class TrainingLogTable(BaseTable):
    training_date = tables.DateColumn(verbose_name="训练日期")
    module = tables.Column(verbose_name="训练模块", accessor="module.name", orderable=True)
    filename = tables.Column(verbose_name="文件名", accessor="filename", orderable=False)
    uploaded_by = tables.Column(verbose_name="上传者", accessor="uploaded_by.first_name", orderable=True)
    actions = ActionsColumn(
        view_url="traininglogs:traininglog_detail",
        delete_url="traininglogs:traininglog_delete",
        view_perm=None,  # None => 不限制查看（列表仅显示自己的记录）, 即显示“查看”按钮
        delete_perm=None,  # None => 不限制删除（安全由后端视图兜底），即显示“删除”按钮
        verbose_name="操作",
    )

    class Meta(BaseTable.Meta):
        model = TrainingLog
        fields = ("training_date", "module", "task", "filename", "uploaded_by", "uploaded_at", "actions")
        order_by = ("-training_date",)


class TrainingLogOthersTable(BaseTable):
    """用于展示他人日志的表格（仅“查看”操作）。"""
    training_date = tables.DateColumn(verbose_name="训练日期")
    module = tables.Column(verbose_name="训练模块", accessor="module.name", orderable=True)
    filename = tables.Column(verbose_name="文件名", accessor="filename", orderable=False)
    uploaded_by = tables.Column(verbose_name="上传者", accessor="uploaded_by.first_name", orderable=True)
    actions = ActionsColumn(
        view_url="traininglogs:traininglog_detail",
        view_perm=None,
        verbose_name="操作",
    )

    class Meta(BaseTable.Meta):
        model = TrainingLog
        fields = ("training_date", "module", "task", "filename", "uploaded_by", "uploaded_at", "actions")
        order_by = ("-training_date",)


class MonthlyStatTable(BaseTable):
    """月度提交统计表：列为 日期 / 已提交选手 / 未提交选手 / 已提交教练。"""

    date = tables.DateColumn(verbose_name="日期", accessor="date", orderable=False)
    submitted_competitors = tables.Column(
        verbose_name="已提交选手",
        orderable=False,
        attrs={
            "td": {
                "class": lambda record: (
                    "text-error"
                    if record.get("submitted_competitors") == "无"
                    else ""
                )
            }
        },
    )
    unsubmitted_competitors = tables.Column(
        verbose_name="未提交选手",
        orderable=False,
        attrs={
            "td": {
                "class": lambda record: (
                    "text-success"
                    if record.get("unsubmitted_competitors") == "全部提交"
                    else ""
                )
            }
        },
    )
    submitted_coaches = tables.Column(
        verbose_name="已提交教练",
        orderable=False,
        attrs={
            "td": {
                "class": lambda record: (
                    "text-error"
                    if record.get("submitted_coaches") == "无"
                    else ""
                )
            }
        },
    )

    class Meta(BaseTable.Meta):
        sequence = ("date", "submitted_competitors", "unsubmitted_competitors", "submitted_coaches")
        row_attrs = {
            "class": lambda record: "hover:bg-base-300 " + ("bg-success/10" if record.get("is_sunday") else "")
        }