# core/tables.py
"""
通用表格组件模块
提供 django-tables2 的基类和常用列类型
"""
from __future__ import annotations

from typing import Any, List

import django_tables2 as tables
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.middleware.csrf import get_token


class BaseDateColumn(tables.DateColumn):
    """自定义日期列，统一日期显示格式为 YYYY-MM-DD（补零）。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Django 日期格式: Y = 4位年, m = 月(补零), d = 日(补零)
        kwargs.setdefault("format", "Y-m-d")
        super().__init__(*args, **kwargs)

class BaseDateTimeColumn(tables.DateTimeColumn):
    """自定义日期时间列，统一显示格式为 YYYY-MM-DD HH:MM:SS（补零）。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Django 日期时间格式: Y = 4位年, m = 月(补零), d = 日(补零), H = 24小时制(补零), i = 分(补零), s = 秒(补零)
        kwargs.setdefault("format", "Y-m-d H:i:s")
        super().__init__(*args, **kwargs)

class BaseTable(tables.Table):
    """表格基类，统一样式配置"""
    
    class Meta:
        template_name = "django-tables2/table.html"
        empty_text = "暂无数据"
        row_attrs = {"class": "hover:bg-base-300"}
        attrs = {
            "class": "table w-full",
            "thead": {"class": "bg-base-300"},
            "tbody": {"class": ""},
            "th": {"class": "text-center whitespace-nowrap"},
            "td": {"class": "align-center text-center"},
        }


class ActionsColumn(tables.Column):
    """通用操作列（DaisyUI 模态确认删除）。

    参数：
        view_url: 详情 named url（如 'app:model_detail'）
        edit_url: 编辑 named url（如 'app:model_edit'）
        delete_url: 删除 named url（如 'app:model_delete'）
        view_perm: 显示"查看"所需权限（默认不校验）
        edit_perm: 显示"编辑"所需权限（默认不校验）
        delete_perm: 显示"删除"所需权限（默认不校验）
        pk_field: URL 主键字段名，默认 'pk'
        view_label: 查看按钮文字，默认 '查看'
        edit_label: 编辑按钮文字，默认 '编辑'
        delete_label: 删除按钮文字，默认 '删除'
        delete_confirm_title: 删除确认对话框标题
        delete_confirm_message: 删除确认对话框消息
    """

    def __init__(
        self,
        view_url: str | None = None,
        edit_url: str | None = None,
        delete_url: str | None = None,
        view_perm: str | None = None,
        edit_perm: str | None = None,
        delete_perm: str | None = None,
        pk_field: str = "pk",
        verbose_name: str = "操作",
        orderable: bool = False,
        attrs: dict[str, Any] | None = None,
        view_label: str = "查看",
        edit_label: str = "编辑",
        delete_label: str = "删除",
        delete_confirm_title: str = "确认删除",
        delete_confirm_message: str = "此操作不可撤销，确定要删除吗？",
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("verbose_name", verbose_name)
        kwargs.setdefault("orderable", orderable)
        kwargs.setdefault("empty_values", ())
        super().__init__(attrs=attrs, **kwargs)
        self.view_url = view_url
        self.edit_url = edit_url
        self.delete_url = delete_url
        self.view_perm = view_perm
        self.edit_perm = edit_perm
        self.delete_perm = delete_perm
        self.pk_field = pk_field
        self.view_label = view_label
        self.edit_label = edit_label
        self.delete_label = delete_label
        self.delete_confirm_title = delete_confirm_title
        self.delete_confirm_message = delete_confirm_message

    def _has_perm(self, user: Any, perm: str | None) -> bool:
        """检查用户是否有指定权限"""
        if perm is None:
            return True  # 未配置权限则不限制
        if not user:
            return False
        return user.has_perm(perm)

    def render(self, value: Any, record: Any = None, table: Any = None, **kwargs: Any) -> str:
        # 获取 request/user
        request = getattr(table, "request", None)
        user = getattr(request, "user", None)

        # URL 与主键
        pk = getattr(record, self.pk_field)
        app_label = getattr(getattr(record, "_meta", None), "app_label", None)
        model_name = getattr(getattr(record, "_meta", None), "model_name", None)
        
        buttons: List[str] = []
        dialogs: List[str] = []

        # 查看按钮
        if self.view_url and self._has_perm(user, self.view_perm):
            try:
                url = reverse(self.view_url, args=[pk])
                buttons.append(
                    f'<a class="btn btn-soft btn-primary btn-xs whitespace-nowrap" href="{url}">{self.view_label}</a>'
                )
            except Exception:
                pass

        # 编辑按钮
        if self.edit_url and self._has_perm(user, self.edit_perm):
            try:
                url = reverse(self.edit_url, args=[pk])
                buttons.append(
                    f'<a class="btn btn-soft btn-warning btn-xs whitespace-nowrap" href="{url}">{self.edit_label}</a>'
                )
            except Exception:
                pass

        # 删除按钮（弹窗确认）
        if self.delete_url and self._has_perm(user, self.delete_perm):
            try:
                del_url = reverse(self.delete_url, args=[pk])
                modal_id = f"modal-del-{app_label}-{model_name}-{pk}"
                csrf = get_token(request) if request else ""
                buttons.append(
                    f'<button class="btn btn-soft btn-error btn-xs whitespace-nowrap" onclick="document.getElementById(\'{modal_id}\').showModal()">{self.delete_label}</button>'
                )
                dialogs.append(
                    "".join([
                        f'<dialog id="{modal_id}" class="modal">',
                        '<div class="modal-box">',
                        f'<h3 class="font-bold text-lg">{self.delete_confirm_title}</h3>',
                        f'<p class="py-2">{self.delete_confirm_message}</p>',
                        f'<form method="post" action="{del_url}">',
                        f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf}">',
                        '<div class="modal-action">',
                        '<button type="submit" class="btn btn-error">确认删除</button>',
                        f'<button type="button" class="btn" onclick="document.getElementById(\'{modal_id}\').close()">取消</button>',
                        '</div>',
                        '</form>',
                        '</div>',
                        '</dialog>',
                    ])
                )
            except Exception:
                pass

        if not buttons:
            return ""

        return mark_safe(
            "".join([
                '<div class="flex flex-col items-center gap-2 sm:flex-row sm:flex-wrap sm:justify-center">',
                "".join(buttons),
                '</div>',
                "".join(dialogs),
            ])
        )



