# traininglogs/tables.py
import django_tables2 as tables
from common.tables import BaseTable
from .models import TrainingLog


class TrainingLogTable(BaseTable):
    training_date = tables.DateColumn(verbose_name="训练日期", format="Y-m-d")
    module = tables.Column(verbose_name="训练模块", accessor="module.name", orderable=True)
    filename = tables.Column(verbose_name="文件名", accessor="filename", orderable=False)
    uploaded_by = tables.Column(verbose_name="上传者", accessor="uploaded_by.first_name", orderable=True)

    class Meta(BaseTable.Meta):
        model = TrainingLog
        fields = ("training_date", "module", "task", "filename", "uploaded_by", "uploaded_at")
        order_by = ("-training_date",)