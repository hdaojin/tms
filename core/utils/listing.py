from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Literal

from django.db.models import Q, QuerySet


@dataclass(frozen=True, slots=True)
class ListFilterSpec:
    """描述一个由通用列表筛选栏渲染的控件。"""

    name: str
    label: str
    control: Literal["select", "search", "date"]
    lookup: str | None = None
    choices: Sequence[tuple[object, object]] | None = None
    empty_label: str = "全部"
    placeholder: str = ""
    advanced: bool = False


class FilterableListMixin:
    """为列表页提供轻量、可复用的 GET 搜索/筛选与 HTMX partial 响应。

    权限与对象可见范围不属于本 mixin 的职责。业务 view 应通过
    ``get_base_queryset()`` 先返回已经收窄权限范围的 queryset，再由本
    mixin 应用用户输入的搜索和筛选条件。
    """

    search_param = "q"
    search_fields: tuple[str, ...] = ()
    list_filter_specs: Sequence[ListFilterSpec] = ()
    search_requires_distinct = False
    always_distinct = False

    htmx_partial_name = "results"
    list_filter_target_id = "list-results"
    list_filter_compact = False
    list_filter_submit = False
    list_filter_htmx = True
    list_filter_status_param: str | None = None
    list_filter_trigger = (
        "submit, change from:.list-filter-select, change from:.list-filter-date, input changed delay:400ms "
        "from:.list-filter-search, search from:.list-filter-search"
    )

    def get_base_queryset(self) -> QuerySet:
        return super().get_queryset()  # type: ignore[misc]

    def get_list_filter_specs(self) -> Sequence[ListFilterSpec]:
        return self.list_filter_specs

    @cached_property
    def resolved_list_filter_specs(self) -> tuple[ListFilterSpec, ...]:
        specs = tuple(self.get_list_filter_specs())
        searches = [spec for spec in specs if spec.control == "search"]
        if len(searches) > 1:
            raise ValueError("列表工具栏最多支持一个搜索控件。")
        return tuple(sorted(specs, key=lambda spec: spec.control != "search"))

    def get_search_query(self) -> str:
        return (self.request.GET.get(self.search_param, "") or "").strip()

    def get_filter_value(self, spec: ListFilterSpec) -> str:
        value = self.request.GET.get(spec.name, "") or ""
        if not value or spec.choices is None:
            return value
        allowed_values = {str(choice[0]) for choice in spec.choices}
        return value if value in allowed_values else ""

    def apply_search(self, queryset: QuerySet) -> QuerySet:
        query = self.get_search_query()
        if not query or not self.search_fields:
            return queryset

        condition = Q()
        for field in self.search_fields:
            condition |= Q(**{f"{field}__icontains": query})
        queryset = queryset.filter(condition)
        if self.search_requires_distinct:
            queryset = queryset.distinct()
        return queryset

    def apply_field_filters(self, queryset: QuerySet) -> QuerySet:
        for spec in self.resolved_list_filter_specs:
            if spec.control != "select" or not spec.lookup:
                continue
            value = self.get_filter_value(spec)
            if value:
                queryset = queryset.filter(**{spec.lookup: value})
        return queryset

    def apply_custom_filters(self, queryset: QuerySet) -> QuerySet:
        """业务页可覆盖此 hook 处理本人范围等非直接字段筛选。"""
        return queryset

    def get_queryset(self) -> QuerySet:
        queryset = self.get_base_queryset()
        queryset = self.apply_search(queryset)
        queryset = self.apply_field_filters(queryset)
        queryset = self.apply_custom_filters(queryset)
        if self.always_distinct:
            queryset = queryset.distinct()
        return queryset

    def get_list_filter_params(self) -> dict[str, str]:
        keys = (self.search_param, *(spec.name for spec in self.resolved_list_filter_specs))
        return {key: self.request.GET.get(key, "") or "" for key in dict.fromkeys(keys)}

    def get_list_filter_controls(self) -> list[dict[str, object]]:
        params = self.get_list_filter_params()
        controls = []
        for spec in self.resolved_list_filter_specs:
            choices = [{"value": str(value), "label": str(label)} for value, label in (spec.choices or ())]
            controls.append(
                {
                    "name": spec.name,
                    "label": spec.label,
                    "type": spec.control,
                    "value": params.get(spec.name, ""),
                    "choices": choices,
                    "empty_label": spec.empty_label,
                    "placeholder": spec.placeholder,
                    "advanced": spec.advanced,
                }
            )
        return controls

    def get_list_filter_url(self, **updates: str) -> str:
        params = self.request.GET.copy()
        allowed = {*self.get_list_filter_params(), "sort"}
        for key in tuple(params):
            if key not in allowed:
                params.pop(key)
        for key, value in updates.items():
            if value:
                params[key] = value
            else:
                params.pop(key, None)
        query = params.urlencode()
        return f"{self.request.path}?{query}" if query else self.request.path

    def get_list_filter_tabs(self) -> list[dict[str, object]]:
        for spec in self.resolved_list_filter_specs:
            if spec.name == self.list_filter_status_param:
                selected = self.get_filter_value(spec)
                return [
                    {
                        "label": label,
                        "href": self.get_list_filter_url(**{spec.name: str(value)}),
                        "active": selected == str(value),
                    }
                    for value, label in (("", spec.empty_label), *(spec.choices or ()))
                ]
        return []

    def get_list_filter_active_items(self) -> list[dict[str, str]]:
        items = []
        for spec in self.resolved_list_filter_specs:
            value = self.get_filter_value(spec)
            if spec.control == "search":
                value = value.strip()
            if value:
                label = next((str(label) for key, label in spec.choices or () if str(key) == value), value)
                items.append(
                    {
                        "label": f"{spec.label}：{label}",
                        "href": self.get_list_filter_url(**{spec.name: ""}),
                    }
                )
        return items

    def get_template_names(self):
        template_names = super().get_template_names()  # type: ignore[misc]
        htmx = getattr(self.request, "htmx", False)
        if (
            self.list_filter_htmx
            and htmx
            and not getattr(htmx, "history_restore_request", False)
            and self.htmx_partial_name
        ):
            return [f"{template_names[0]}#{self.htmx_partial_name}"]
        return template_names

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        controls = self.get_list_filter_controls()
        advanced = [control for control in controls if control.get("advanced")]
        status = self.list_filter_status_param
        active_status = next((control["value"] for control in controls if control["name"] == status), "")
        context.update(
            {
                "list_filters": self.get_list_filter_params(),
                "list_filter_controls": [
                    control for control in controls if not control.get("advanced") and control["name"] != status
                ],
                "list_filter_advanced_controls": advanced,
                "list_filter_advanced_expanded": any(control["value"] for control in advanced),
                "list_filter_active_items": self.get_list_filter_active_items() if advanced else [],
                "list_filter_tabs": self.get_list_filter_tabs() if status else [],
                "list_filter_hidden_fields": [{"name": status, "value": active_status}] if active_status else [],
                "list_filter_url": self.request.path,
                "list_filter_target_id": self.list_filter_target_id,
                "list_filter_trigger": self.list_filter_trigger,
                "list_filter_compact": self.list_filter_compact,
                "list_filter_submit": self.list_filter_submit,
                "list_filter_htmx_disabled": not self.list_filter_htmx,
            }
        )
        return context
