# meeting/tables.py
import django_tables2 as tables
from core.utils.tables import BaseTable, BaseDateColumn, BaseDateTimeColumn, ActionsColumn
from .models import Meeting

class MeetingTable(BaseTable):
    date = BaseDateColumn(verbose_name="会议日期")
    filename = tables.Column(verbose_name="文件名", accessor="filename", orderable=False)
    uploaded_by = tables.Column(verbose_name="上传者", accessor="uploaded_by.display_name", orderable=True)
    uploaded_at = BaseDateTimeColumn(verbose_name="上传时间", accessor="uploaded_at")
    actions = ActionsColumn(
        view_url="meeting:meeting_detail",
        delete_url="meeting:meeting_delete",
        view_perm=None,  # None => 不限制查看
        delete_perm="meeting.delete_meeting",
        # pk_field="pk",
        verbose_name="操作",
    )
    class Meta(BaseTable.Meta):
        model = Meeting
        fields = ("date", "title", "filename", "uploaded_by", "uploaded_at", "actions")
        order_by = ("-date",)
