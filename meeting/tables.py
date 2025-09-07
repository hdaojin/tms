# meeting/tables.py
import django_tables2 as tables
from common.tables import BaseTable
from .models import Meeting

class MeetingTable(BaseTable):
    date = tables.DateColumn(verbose_name="会议日期", format="Y-m-d")
    filename = tables.Column(verbose_name="文件名", accessor="filename", orderable=False)
    uploaded_by = tables.Column(verbose_name="上传者", accessor="uploaded_by.first_name", orderable=True)
    class Meta(BaseTable.Meta):
        model = Meeting
        fields = ("date", "title", "filename", "uploaded_by", "uploaded_at")
        order_by = ("-date",)
