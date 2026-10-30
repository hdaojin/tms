import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html

from accounts.tables import UserListTable

from .models import TrainingCycleMember


class CycleCandidateTable(UserListTable):
    username = tables.Column(verbose_name="账号")

    class Meta(UserListTable.Meta):
        fields = ("selection", "first_name", "username", "roles", "join_date")
        sequence = fields
        exclude = ("row_number", "gender", "birth_date", "phone_number", "school_dormitory",
                   "leave_date", "activation_status", "actions")
        order_by = ("-join_date",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.columns["roles"].column.orderable = False


class CycleMemberTable(CycleCandidateTable):
    member_role = tables.Column(verbose_name="周期身份")
    member_current = tables.BooleanColumn(verbose_name="当前周期", yesno=("是", "否"))
    member_actions = tables.Column(verbose_name="操作", empty_values=(), orderable=False)

    def render_member_role(self, value):
        return TrainingCycleMember.Role(value).label

    def render_member_actions(self, record):
        links = []
        for permission, url, label in (
            ("change", "training:member_edit", "维护"), ("delete", "training:member_delete", "移除"),
        ):
            if self.request.user.has_perm(f"training.{permission}_trainingcyclemember"):
                links.append(format_html('<a class="btn btn-outline btn-sm" href="{}">{}</a>',
                                         reverse(url, args=[record.member_cycle_id, record.member_pk]), label))
        return format_html("{} {}", *(links + [""] * (2 - len(links))))

    class Meta(CycleCandidateTable.Meta):
        fields = ("first_name", "username", "roles", "join_date", "member_role", "member_current", "member_actions")
        sequence = fields
        exclude = (*CycleCandidateTable.Meta.exclude, "selection")
