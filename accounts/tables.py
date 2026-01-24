# accounts/tables.py
import django_tables2 as tables
from django.contrib.auth import get_user_model
from core.utils.tables import BaseTable, BaseDateColumn

User = get_user_model()


class UserListTable(BaseTable):
    """用户列表表格，包含用户基本信息和关联的 Profile 信息。"""

    # 序号列
    row_number = tables.Column(
        verbose_name="序号", empty_values=(), orderable=False
    )

    # 姓名（从 User.first_name 获取）
    first_name = tables.Column(
        verbose_name="姓名",
        attrs={"td": {"class": "min-w-20 whitespace-nowrap"}}
    )

    # Profile 字段
    name_pronunciation = tables.Column(
        verbose_name="姓名全拼", accessor="profile__name_pronunciation", orderable=True
    )
    student_id = tables.Column(
        verbose_name="学号", accessor="profile__student_id", orderable=True
    )
    gender = tables.Column(
        verbose_name="性别", accessor="profile__get_gender_display", orderable=False
    )
    birth_date = BaseDateColumn(
        verbose_name="出生日期", accessor="profile__birth_date", orderable=True
    )
    phone_number = tables.Column(
        verbose_name="电话号码", accessor="profile__phone_number", orderable=True
    )
    id_number = tables.Column(
        verbose_name="身份证号", accessor="profile__id_number", orderable=False
    )
    emergency_contact = tables.Column(
        verbose_name="紧急联系人", accessor="profile__emergency_contact", orderable=False
    )
    emergency_contact_phone = tables.Column(
        verbose_name="紧急联系人电话", accessor="profile__emergency_contact_phone", orderable=False
    )
    emergency_contact_relation = tables.Column(
        verbose_name="紧急联系人关系", accessor="profile__emergency_contact_relation", orderable=False
    )
    address = tables.Column(
        verbose_name="家庭住址", accessor="profile__address", orderable=False
    )
    original_class = tables.Column(
        verbose_name="原班级", accessor="profile__original_class", orderable=True
    )
    original_headteacher = tables.Column(
        verbose_name="原班主任", accessor="profile__original_headteacher", orderable=False
    )
    original_headteacher_phone = tables.Column(
        verbose_name="原班主任电话", accessor="profile__original_headteacher_phone", orderable=False
    )
    school_dormitory = tables.Column(
        verbose_name="宿舍", accessor="profile__school_dormitory", orderable=False
    )
    join_date = BaseDateColumn(
        verbose_name="入读日期", accessor="profile__join_date", orderable=True
    )
    leave_date = BaseDateColumn(
        verbose_name="离开日期", accessor="profile__leave_date", orderable=True
    )
    notes = tables.Column(
        verbose_name="备注", accessor="profile__notes", orderable=False
    )

    def render_row_number(self, record, value, bound_column, bound_row):
        """渲染序号列，从1开始计数。"""
        # 获取当前页的起始索引
        page = getattr(self, "page", None)
        if page is not None:
            start_index = page.start_index()
        else:
            start_index = 1
        # bound_row.row_counter 是从0开始的行索引
        return start_index + bound_row.row_counter

    class Meta(BaseTable.Meta):
        model = User
        fields = (
            "row_number",
            "first_name",
            "name_pronunciation",
            "student_id",
            "gender",
            "birth_date",
            "phone_number",
            "id_number",
            "emergency_contact",
            "emergency_contact_phone",
            "emergency_contact_relation",
            "address",
            "original_class",
            "original_headteacher",
            "original_headteacher_phone",
            "school_dormitory",
            "join_date",
            "leave_date",
            "notes",
        )
        order_by = ("join_date",)
