# core/mixins.py
"""
自定义类视图混入模块
提供一些常用的类视图混入
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


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
                    # 支持日期/时间等对象格式化：在模板中使用 {date:%Y-%m-%d} 即可
                    # 关键点：不要提前 str()，否则失去 __format__ 能力
                    value = getattr(self.object, field, '')  # type: ignore
                    field_values[field] = value if value is not None else ''
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
