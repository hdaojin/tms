from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.db.models import Q, QuerySet


class FilterableListMixin:
    """为列表页提供轻量、可复用的 GET 搜索/筛选与 HTMX partial 响应。

    权限与对象可见范围不属于本 mixin 的职责。业务 view 应通过
    ``get_base_queryset()`` 先返回已经收窄权限范围的 queryset，再由本
    mixin 应用用户输入的搜索和筛选条件。
    """

    search_param = "q"
    search_fields: tuple[str, ...] = ()
    filter_fields: Mapping[str, str] = {}
    filter_choices: Mapping[str, Iterable[tuple[object, object]]] = {}
    extra_filter_params: tuple[str, ...] = ()
    search_requires_distinct = False
    always_distinct = False

    htmx_partial_name = "results"
    list_filter_target_id = "list-results"
    list_filter_indicator_id = "list-filter-indicator"
    list_filter_controls_template: str | None = None
    list_filter_trigger = "submit"
    list_filter_form_class = "rounded-box border border-base-300 bg-base-100 p-3 shadow-sm"

    def get_base_queryset(self) -> QuerySet:
        return super().get_queryset()  # type: ignore[misc]

    def get_search_query(self) -> str:
        return (self.request.GET.get(self.search_param, "") or "").strip()

    def get_filter_value(self, param: str) -> str:
        value = self.request.GET.get(param, "") or ""
        choices = self.filter_choices.get(param)
        if not value or choices is None:
            return value
        allowed_values = {str(choice[0]) for choice in choices}
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
        for param, lookup in self.filter_fields.items():
            value = self.get_filter_value(param)
            if value:
                queryset = queryset.filter(**{lookup: value})
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
        keys = (self.search_param, *self.filter_fields.keys(), *self.extra_filter_params)
        return {key: self.request.GET.get(key, "") or "" for key in dict.fromkeys(keys)}

    def get_template_names(self):
        template_names = super().get_template_names()  # type: ignore[misc]
        if getattr(self.request, "htmx", False) and self.htmx_partial_name:
            return [f"{template_names[0]}#{self.htmx_partial_name}"]
        return template_names

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        context.update(
            {
                "list_filters": self.get_list_filter_params(),
                "list_filter_url": self.request.path,
                "list_filter_target_id": self.list_filter_target_id,
                "list_filter_indicator_id": self.list_filter_indicator_id,
                "list_filter_controls_template": self.list_filter_controls_template,
                "list_filter_trigger": self.list_filter_trigger,
                "list_filter_form_class": self.list_filter_form_class,
            }
        )
        return context
