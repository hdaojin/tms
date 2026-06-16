# accounts/tables.py
import django_tables2 as tables
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from accounts.services.users import get_user_display_name, get_user_role_badges
from core.permissions import get_permission_bundle_specs
from core.utils.tables import BaseTable, BaseDateColumn, ActionsColumn

User = get_user_model()
PERMISSION_BUNDLE_NAMES = {
    spec.code: spec.name for spec in get_permission_bundle_specs()
}


class UserListTable(BaseTable):
    """用户列表表格，只显示关键信息，详细信息通过链接查看。"""

    # 序号列
    row_number = tables.Column(
        verbose_name="序号", empty_values=(), orderable=False
    )

    # 姓名（从 User.first_name 获取）
    first_name = tables.Column(
        verbose_name="姓名",
        empty_values=(),
        attrs={"td": {"class": "min-w-20 whitespace-nowrap text-center align-middle"}},
    )
    roles = tables.Column(
        verbose_name="角色",
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "min-w-28 whitespace-nowrap text-center align-middle"}},
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
    activation_status = tables.Column(
        verbose_name="激活",
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "whitespace-nowrap text-center align-middle"}},
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

    def render_first_name(self, record):
        return get_user_display_name(record)

    def render_roles(self, record):
        role_badges = get_user_role_badges(record, size="badge-sm")

        return format_html(
            '<div class="flex flex-wrap justify-center gap-1">{}</div>',
            format_html_join(
                "",
                '<span class="{}">{}</span>',
                (
                    (
                        role_badge["css_class"],
                        role_badge["label"],
                    )
                    for role_badge in role_badges
                ),
            ),
        )

    def render_activation_status(self, record):
        if record.is_active:
            return mark_safe(
                '<span class="inline-flex items-center justify-center" title="有效" aria-label="有效">'
                '<span class="icon-[tabler--circle-check-filled] size-5 text-success"></span>'
                "</span>"
            )
        return mark_safe(
            '<span class="inline-flex items-center justify-center" title="无效" aria-label="无效">'
            '<span class="icon-[tabler--circle-x-filled] size-5 text-error"></span>'
            "</span>"
        )

    class Meta(BaseTable.Meta):
        model = User
        fields = (
            "row_number",
            "first_name",
            "roles",
            "gender",
            "birth_date",
            "phone_number",
            "school_dormitory",
            "join_date",
            "leave_date",
            "activation_status",
            "actions",
        )


class RoleListTable(BaseTable):
    """角色列表表格，展示用户组及其扩展信息。"""

    row_number = tables.Column(
        verbose_name="序号", empty_values=(), orderable=False
    )
    name = tables.Column(
        verbose_name="角色",
        attrs={"td": {"class": "min-w-24 whitespace-nowrap text-center align-middle"}},
    )
    codename = tables.Column(
        verbose_name="英文标识",
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "min-w-28 whitespace-nowrap text-center align-middle"}},
    )
    description = tables.Column(
        verbose_name="描述",
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "min-w-48 text-center align-middle"}},
    )
    user_total = tables.Column(
        verbose_name="用户数",
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "whitespace-nowrap text-center align-middle"}},
    )
    permission_bundles = tables.Column(
        verbose_name="业务权限包",
        empty_values=(),
        orderable=False,
        attrs={"td": {"class": "min-w-56 text-center align-middle"}},
    )

    def render_row_number(self, record, value, bound_column, bound_row):
        page = getattr(self, "page", None)
        start_index = page.start_index() if page is not None else 1
        return start_index + bound_row.row_counter

    def _get_profile(self, record):
        return getattr(record, "profile", None)

    def render_codename(self, record):
        profile = self._get_profile(record)
        return getattr(profile, "codename", "") or "-"

    def render_description(self, record):
        profile = self._get_profile(record)
        return getattr(profile, "description", "") or "-"

    def render_user_total(self, record):
        return getattr(record, "user_total", 0)

    def render_permission_bundles(self, record):
        profile = self._get_profile(record)
        bundle_codes = getattr(profile, "selected_permission_bundles", None) or []
        bundle_names = [
            PERMISSION_BUNDLE_NAMES.get(code, code)
            for code in bundle_codes
        ]
        return "、".join(bundle_names) or "无"

    class Meta(BaseTable.Meta):
        model = Group
        fields = (
            "row_number",
            "name",
            "codename",
            "description",
            "user_total",
            "permission_bundles",
        )
