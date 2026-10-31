# meetings/tables.py
import django_tables2 as tables
from core.tables import ActionsColumn, BaseDateColumn, BaseDateTimeColumn, BaseTable
from .models import Meeting
from urllib.parse import urlencode
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe


class MeetingActionsColumn(ActionsColumn):
    def render(self, value, record=None, table=None, **kwargs):
        request = getattr(table, "request", None)
        user = getattr(request, "user", None)
        query = request.GET.urlencode() if request else ""
        # 每行均已由 selector 收窄至可见记录；沿用基础权限判断，避免逐行查权限范围。
        actions = [
            {
                "href": reverse("meetings:meeting_detail", args=[record.pk]),
                "label": "查看",
                "variant_class": "btn-soft btn-primary",
            }
        ]
        if self._has_perm(user, self.edit_perm):
            actions.append(
                {
                    "href": reverse("meetings:meeting_audience", args=[record.pk])
                    + "?"
                    + urlencode({"return_query": query}),
                    "label": self.edit_label,
                    "variant_class": "btn-soft btn-warning",
                }
            )
        confirmations = []
        if self._has_perm(user, self.delete_perm):
            confirmations.append(
                {
                    "href": reverse("meetings:meeting_delete", args=[record.pk]),
                    "label": self.delete_label,
                    "variant_class": "btn-soft btn-error",
                    "modal_id": f"meeting-delete-{record.pk}",
                    "title": self.delete_confirm_title,
                    "message": self.delete_confirm_message,
                    "confirm_label": "确认删除",
                }
            )
        # 组件仅需 CSRF，不为每行重新执行包含数据库查询的全局 context processors。
        return mark_safe(
            render_to_string(
                "components/table_actions.html",
                {
                    "actions": actions,
                    "confirm_actions": confirmations,
                    "csrf_token": get_token(request) if request else "",
                },
            )
        )


class MeetingTable(BaseTable):
    date = BaseDateColumn(verbose_name="会议日期")
    filename = tables.Column(verbose_name="文件名", accessor="filename", orderable=False)
    uploaded_by = tables.Column(
        verbose_name="上传者",
        accessor="uploaded_by__display_name",
        orderable=True,
        order_by=("uploaded_by__last_name", "uploaded_by__first_name", "uploaded_by__username"),
    )
    uploaded_at = BaseDateTimeColumn(verbose_name="上传时间", accessor="uploaded_at")
    is_public = tables.BooleanColumn(verbose_name="可见范围", yesno="所有人可见,限定人员可见", orderable=False)
    actions = MeetingActionsColumn(
        view_url="meetings:meeting_detail",
        delete_url="meetings:meeting_delete",
        view_perm=None,  # None => 不限制查看
        delete_perm="meetings.delete_meeting",
        edit_url="meetings:meeting_audience",
        edit_perm="meetings.change_meeting",
        edit_label="设置可见人员",
        # pk_field="pk",
        verbose_name="操作",
    )

    class Meta(BaseTable.Meta):
        model = Meeting
        fields = ("date", "title", "filename", "uploaded_by", "uploaded_at", "is_public", "actions")
        order_by = ("-date",)
