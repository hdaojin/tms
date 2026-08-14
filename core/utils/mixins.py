# core/mixins.py
"""
自定义类视图混入模块
提供一些常用的类视图混入
"""
from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404
from django.urls import reverse

class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    仅允许超级用户访问的混入
    用法:
        class MyView(SuperuserRequiredMixin, View):
            ...
    """
    raise_exception = True  # If True, raise PermissionDenied on failure, else redirect to login
    
    def test_func(self) -> bool:
        return self.request.user.is_superuser  # type: ignore


class OwnerRequiredMixin:
    """
    仅允许对象所有者访问的混入
    
    用法:
        class MyDeleteView(OwnerRequiredMixin, DeleteView):
            owner_field = "uploaded_by"
            ...
    """
    owner_field: str = "uploaded_by"
    
    def get_object(self, queryset: Any = None) -> Any:
        """重写 get_object，仅允许所有者访问"""
        obj = super().get_object(queryset)  # type: ignore
        user = self.request.user  # type: ignore
        
        # 超级管理员放行
        if getattr(user, 'is_superuser', False):
            return obj
        
        owner_id = getattr(obj, f'{self.owner_field}_id', None)
        if owner_id != getattr(user, 'pk', None):
            raise Http404
        return obj


class TitleMixin:
    """
    为类视图添加标题的混入
    
    使用模板字符串统一处理所有标题场景：
    
    用法:
        # 静态标题
        class MyView(TitleMixin, View):
            title = "我的页面"
        
        # 使用对象字段（自动检测 {field} 占位符）
        class MyDetailView(TitleMixin, DetailView):
            title = "{name}"  # 等价于 object.name
        
        # 多个字段拼接
        class MyDetailView(TitleMixin, DetailView):
            title = "{date} - {title}"  # 自动从对象获取字段值
        
        # 复杂格式化（支持 Python 格式规范）
        class MyDetailView(TitleMixin, DetailView):
            title = "{date:%Y年%m月%d日} 的 {title} 会议记录"
    """
    title: str | None = None
    title_icon: str = "icon-[tabler--circle-letter-t]"  # 标题图标

    def get_title(self) -> str | None:
        if not self.title:
            return None
        
        # 检查是否有对象字段占位符 {xxx}
        if '{' in self.title and hasattr(self, 'object') and self.object:  # type: ignore
            try:
                # 构建字段值字典
                import re
                field_names = re.findall(r'\{(\w+)(?::[^}]*)?\}', self.title)
                field_values = {}
                for field in field_names:
                    value = getattr(self.object, field, None)  # type: ignore
                    field_values[field] = value if value is not None else ''
                return self.title.format(**field_values)
            except (KeyError, ValueError, AttributeError):
                pass
        
        return self.title
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore
        context['title'] = self.get_title()
        context['title_icon'] = self.title_icon
        return context


class UploadedDocumentCreateMixin:
    """为上传类 CreateView 统一写入上传者与成功提示。"""

    uploaded_by_field: str = 'uploaded_by'
    success_message: str | None = None

    def prepare_document_for_save(self, form: Any) -> None:
        """子类可覆盖以补充保存前准备逻辑。"""

    def form_valid(self, form: Any):
        if getattr(form.instance, f'{self.uploaded_by_field}_id', None) is None:
            setattr(form.instance, self.uploaded_by_field, self.request.user)  # type: ignore[attr-defined]

        self.prepare_document_for_save(form)
        response = super().form_valid(form)  # type: ignore[misc]
        if self.success_message:
            messages.success(self.request, self.success_message)  # type: ignore[attr-defined]
        return response


class PdfPreviewDetailMixin:
    """为文档详情页补充统一的 PDF 预览上下文。"""

    document_context_name: str = 'document'
    pdf_preview_url_name: str | None = None

    def get_pdf_preview_url(self) -> str | None:
        if not self.pdf_preview_url_name:
            return None
        return reverse(self.pdf_preview_url_name, args=[self.object.pk])  # type: ignore[attr-defined]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        context[self.document_context_name] = self.object  # type: ignore[attr-defined]
        context['pdf_preview_url'] = self.get_pdf_preview_url()
        return context


class CreatedUpdatedAdminMixin:
    """为 admin 保存动作统一写入创建人与更新人。"""

    created_by_field = 'created_by'
    updated_by_field = 'updated_by'

    def save_model(self, request, obj, form, change):
        if not change and hasattr(obj, self.created_by_field):
            if getattr(obj, f'{self.created_by_field}_id', None) is None:
                setattr(obj, self.created_by_field, request.user)
        elif change and hasattr(obj, self.updated_by_field):
            setattr(obj, self.updated_by_field, request.user)

        super().save_model(request, obj, form, change)
