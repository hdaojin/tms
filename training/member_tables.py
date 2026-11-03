import django_tables2 as tables
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html

from accounts.tables import UserListTable
from core.tables import BaseDateColumn

from .models import TrainingCycleMember


class AgeColumn(tables.Column):
    def render(self, value):
        today = timezone.localdate()
        return today.year - value.year - ((today.month, today.day) < (value.month, value.day))


class CycleCandidateTable(UserListTable):
    class Meta(UserListTable.Meta):
        fields = ("selection", "first_name", "roles", "join_date")
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
        fields = ("first_name", "roles", "join_date", "member_role", "member_current", "member_actions")
        sequence = fields
        exclude = (*CycleCandidateTable.Meta.exclude, "selection")


class PlanCandidateTable(CycleCandidateTable):
    birth_date = BaseDateColumn(verbose_name="出生日期", accessor="profile__birth_date", orderable=True)
    age = AgeColumn(verbose_name="年龄", accessor="profile__birth_date", orderable=False)

    def render_first_name(self, record):
        return record.identity_label or super().render_first_name(record)

    def render_selection(self, record):
        if record.identity_invalid:
            return format_html('<span title="同名备注未填写或重复">无法区分</span>')
        return super().render_selection(record)

    class Meta(CycleCandidateTable.Meta):
        fields = ("selection", "first_name", "roles", "birth_date", "age", "join_date")
        sequence = fields
        exclude = tuple(field for field in CycleCandidateTable.Meta.exclude if field != "birth_date")


class PlanMemberTable(PlanCandidateTable):
    participating = tables.BooleanColumn(verbose_name="参与中", yesno=("是", "否"))
    member_actions = tables.TemplateColumn(template_name="training/partials/plan_member_action.html",
                                           verbose_name="操作", orderable=False)

    class Meta(PlanCandidateTable.Meta):
        fields = ("first_name", "roles", "birth_date", "age", "join_date", "participating", "member_actions")
        sequence = fields
        exclude = (*PlanCandidateTable.Meta.exclude, "selection")
