# common/mixins.py
"""
自定义类视图混入模块
提供一些常用的类视图混入
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from urllib.parse import urlencode
from django.views.generic import ListView
from django.db.models import Q
from django.utils.html import format_html
from django.template.loader import render_to_string
from django.http import HttpResponse

class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    仅允许超级用户访问的混入
    用法:
        class MyView(SuperuserRequiredMixin, View):
            ...
    """
    raise_exception = True  # If True, raise PermissionDenied on failure, else redirect to login
    def test_func(self):
        return self.request.user.is_superuser # type: ignore



class TitleMixin:
    """
    为类视图添加标题的混入
    用法:
        class MyView(TitleMixin, View):
            title = "My Page Title"
            ...
        
        # 使用单个字段作为标题
        class MyDetailView(TitleMixin, DetailView):
            title_object_field = "name"
            ...
        
        # 使用多个字段拼接作为标题
        class MyDetailView(TitleMixin, DetailView):
            title_object_fields = ["date", "title"]  # 将拼接为 "2024-01-01 - 会议标题"
            title_separator = " - "  # 自定义分隔符，默认为 " - "
            ...
        
        # 使用模板字符串格式化标题
        class MyDetailView(TitleMixin, DetailView):
            title_object_fields = ["date", "title"]
            title_template = "{date} 的 {title}"  # 将格式化为 "2024-01-01 的 会议标题"
            ...
    """
    title = None
    title_object_field = None  # 单个字段名（向后兼容）
    title_object_fields = None  # 多个字段名列表
    title_separator = " - "  # 多字段拼接时的分隔符
    title_template = None  # 模板字符串，如 "{field1} 的 {field2}"
    title_icon = "icon-[tabler--circle-letter-t]" # 标题图标，默认为圆形 "T" 图标

    def get_title(self):
        if hasattr(self, 'object') and self.object:  # type: ignore
            # 优先使用模板字符串格式化
            if self.title_template and self.title_object_fields:
                field_values = {}
                for field in self.title_object_fields:  # type: ignore
                    field_values[field] = str(getattr(self.object, field, ''))  # type: ignore
                try:
                    return self.title_template.format(**field_values)
                except (KeyError, ValueError):
                    # 如果模板格式化失败，回退到拼接方式
                    pass
            
            # 使用多字段拼接
            if self.title_object_fields:
                field_values = []
                for field in self.title_object_fields:  # type: ignore
                    value = getattr(self.object, field, None)  # type: ignore
                    if value:
                        field_values.append(str(value))
                if field_values:
                    return self.title_separator.join(field_values)
            
            # 向后兼容：使用单个字段
            if self.title_object_field:
                return str(getattr(self.object, self.title_object_field, ''))  # type: ignore
        
        return self.title
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore
        context['title'] = self.get_title()
        context['title_icon'] = self.title_icon
        return context




class TableMixin:
    # —— 基础表格配置 ——
    table_headers: list[str] = []
    table_css_classes: str = ""
    table_empty_text: str = "暂无数据"
    table_zone_id: str = "table-zone"

    # —— 搜索 ——（模糊匹配）
    search_fields: list[str] = []   # e.g. ["title", "user__username"]

    # —— 排序 ——（“显示名/键” -> ORM 字段）
    table_sort_map: dict[str, str] = {}  # e.g. {"日期": "date"}
    default_sort: str = "-id"            # e.g. "-date"

    # —— 工具：输出统一风格按钮（可选） ——
    @staticmethod
    def fmt_btn(url: str, text: str, size="xs", color="primary"):
        return format_html('<a href="{}" class="btn btn-{} btn-{}">{}</a>', url, size, color, text)

    # 搜索 + 排序 应用到 queryset
    def build_queryset(self, base_qs):
        request = self.request
        q = (request.GET.get("q") or "").strip()
        if q and self.search_fields:
            cond = Q()
            for f in self.search_fields:
                cond |= Q(**{f"{f}__icontains": q})
            base_qs = base_qs.filter(cond)

        sort_key = request.GET.get("sort")
        order = request.GET.get("order", "desc")  # asc/desc

        if not sort_key:
            return base_qs.order_by(self.default_sort)

        orm_field = self.table_sort_map.get(sort_key) or sort_key
        if order == "desc" and not orm_field.startswith("-"):
            orm_field = f"-{orm_field}"
        elif order == "asc" and orm_field.startswith("-"):
            orm_field = orm_field.lstrip("-")

        return base_qs.order_by(orm_field)

    def get_queryset(self):
        return self.build_queryset(super().get_queryset())

    # 构造表头控件（含 hx-get 链接）
    def build_header_controls(self):
        req = self.request
        current_sort = req.GET.get("sort")
        current_order = req.GET.get("order", "desc")
        q = req.GET.get("q", "")

        controls = []
        for label in self.table_headers:
            sort_key = label if label in self.table_sort_map else None
            is_active = (current_sort == sort_key) if sort_key else False
            next_order = "asc" if (is_active and current_order == "desc") else "desc"

            query = {}
            if sort_key:
                query.update({"sort": sort_key, "order": next_order})
            if q:
                query["q"] = q

            hx_get = f"{req.path}?{urlencode(query)}" if query else ""
            controls.append({
                "label": label,
                "sort_key": sort_key,
                "is_active": is_active,
                "current_order": (current_order if is_active else "desc"),
                "hx_get": hx_get,
            })
        return controls

    # 构造保留查询串（用于分页链接拼接）
    def build_qs_base(self):
        params = self.request.GET.copy()
        params.pop("page", None)
        return urlencode({k: v for k, v in params.items() if v})

    # 由子类实现：把 queryset -> rows
    def get_table_rows(self, queryset) -> list[list]:
        raise NotImplementedError

    # 渲染上下文
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = ctx.get(self.get_context_object_name(self.object_list), self.object_list)
        ctx.update({
            "headers": self.table_headers,
            "rows": self.get_table_rows(qs),
            "table_css_classes": self.table_css_classes,
            "table_empty_text": self.table_empty_text,
            "header_controls": self.build_header_controls(),
            "table_zone_id": self.table_zone_id,
            "qs_base": self.build_qs_base(),
        })
        return ctx

    # 可选优化：HTMX 请求时只返回表格片段，减少带宽
    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("HX-Request") == "true":
            html = render_to_string("components/table.html", context, request=self.request)
            return HttpResponse(html)
        return super().render_to_response(context, **response_kwargs)


class TableListView(TableMixin, ListView):
    """直接继承这个类来写你的列表页"""
    pass
