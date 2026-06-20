"""
django-tables2 基础表格组件。

新 TMS 列表页统一从本模块导入 BaseTable/BaseDateColumn/BaseDateTimeColumn/ActionsColumn。
"""
from __future__ import annotations

from typing import Any

import django_tables2 as tables
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe


class BaseDateColumn(tables.DateColumn):
    """统一日期列显示格式。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("format", "Y-m-d")
        super().__init__(*args, **kwargs)


class BaseDateTimeColumn(tables.DateTimeColumn):
    """统一日期时间列显示格式。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("format", "Y-m-d H:i:s")
        super().__init__(*args, **kwargs)


class BaseTable(tables.Table):
    """DaisyUI 风格表格基类。"""

    class Meta:
        template_name = "django_tables2/tms.html"
        empty_text = "暂无数据"
        row_attrs = {"class": "hover:bg-base-200"}
        attrs = {
            "class": "table w-full",
            "thead": {"class": "bg-base-200"},
            "th": {"class": "text-center whitespace-nowrap"},
            "td": {"class": "text-center align-middle"},
        }


class ActionsColumn(tables.Column):
    """通用操作列。

    参数:
    - view_url/edit_url/delete_url: named URL。
    - *_perm: 对应操作权限；为空则不限制。
    - pk_field: URL 主键字段名，默认 pk。
    - *_label: 按钮文字。
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
        delete_confirm_message: str = "此操作不可撤销，确定要继续吗？",
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
        if perm is None:
            return True
        return bool(user and user.has_perm(perm))

    def _resolve_action(self, url_name: str | None, pk: Any) -> str | None:
        if not url_name:
            return None
        try:
            return reverse(url_name, args=[pk])
        except NoReverseMatch:
            return None

    def render(self, value: Any, record: Any = None, table: Any = None, **kwargs: Any) -> str:
        request = getattr(table, "request", None)
        user = getattr(request, "user", None)
        pk = getattr(record, self.pk_field)
        app_label = getattr(getattr(record, "_meta", None), "app_label", "item")
        model_name = getattr(getattr(record, "_meta", None), "model_name", "record")

        actions: list[dict[str, str]] = []
        confirm_actions: list[dict[str, str]] = []

        if self._has_perm(user, self.view_perm):
            href = self._resolve_action(self.view_url, pk)
            if href:
                actions.append({"href": href, "label": self.view_label, "variant_class": "btn-soft btn-primary"})

        if self._has_perm(user, self.edit_perm):
            href = self._resolve_action(self.edit_url, pk)
            if href:
                actions.append({"href": href, "label": self.edit_label, "variant_class": "btn-soft btn-warning"})

        if self._has_perm(user, self.delete_perm):
            href = self._resolve_action(self.delete_url, pk)
            if href:
                confirm_actions.append(
                    {
                        "href": href,
                        "label": self.delete_label,
                        "variant_class": "btn-soft btn-error",
                        "modal_id": f"modal-del-{app_label}-{model_name}-{pk}",
                        "title": self.delete_confirm_title,
                        "message": self.delete_confirm_message,
                        "confirm_label": "确认删除",
                    }
                )

        if not actions and not confirm_actions:
            return ""

        template_request = request if hasattr(request, "META") else None
        return mark_safe(
            render_to_string(
                "components/table_actions.html",
                {"actions": actions, "confirm_actions": confirm_actions},
                request=template_request,
            )
        )
