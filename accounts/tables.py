# accounts/tables.py
import django_tables2 as tables
from django.contrib.auth import get_user_model
from core.utils.tables import BaseTable, BaseDateColumn, ActionsColumn

User = get_user_model()


class UserListTable(BaseTable):
    """用户列表表格，只显示关键信息，详细信息通过链接查看。"""

    # 序号列
    row_number = tables.Column(
        verbose_name="序号", empty_values=(), orderable=False
    )

    # 姓名（从 User.first_name 获取）
    first_name = tables.Column(
        verbose_name="姓名",
        attrs={"td": {"class": "min-w-20 whitespace-nowrap"}}
    )

    # 关键 Profile 字段
    gender = tables.Column(
        verbose_name="性别", accessor="profile__get_gender_display", orderable=False
    )
    birth_date = BaseDateColumn(
        verbose_name="出生日期", accessor="profile__birth_date", orderable=True
    )
    phone_number = tables.Column(
        verbose_name="电话号码", accessor="profile__phone_number", orderable=True
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

    # 操作列
    actions = ActionsColumn(
        view_url="accounts:user_detail",
        view_label="详细信息",
        view_perm="accounts.view_all_profiles",
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
            "gender",
            "birth_date",
            "phone_number",
            "school_dormitory",
            "join_date",
            "leave_date",
            "actions",
        )
        order_by = ("join_date",)
