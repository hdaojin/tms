# core/mixins.py
"""
自定义类视图混入模块
提供一些常用的类视图混入
"""
from __future__ import annotations

from typing import Any, Set

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404

from core.constants import GROUP_COACH, GROUP_COMPETITOR


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


class CrossGroupAccessMixin:
    """
    跨组访问权限混入
    
    实现选手和教练之间的互相查看权限：
    - 超级管理员可以查看所有内容
    - 用户可以查看自己的内容
    - 选手可以查看教练的内容
    - 教练可以查看选手的内容
    
    用法:
        class MyDetailView(CrossGroupAccessMixin, DetailView):
            owner_field = "uploaded_by"  # 对象所有者字段名
            ...
    """
    owner_field: str = "uploaded_by"  # 所有者字段名，子类可覆盖
    
    def get_user_groups(self, user: Any) -> Set[str]:
        """获取用户所属的组名集合"""
        if not user or not getattr(user, 'pk', None):
            return set()
        groups = getattr(user, 'groups', None)
        if groups is None:
            return set()
        return set(groups.values_list('name', flat=True))
    
    def check_cross_group_access(self, obj: Any) -> bool:
        """
        检查当前用户是否有权访问指定对象
        
        Args:
            obj: 要检查访问权限的对象
            
        Returns:
            bool: 是否有访问权限
        """
        user = self.request.user  # type: ignore
        
        # 超级管理员放行
        if getattr(user, 'is_superuser', False):
            return True
        
        # 获取对象所有者
        owner = getattr(obj, self.owner_field, None)
        owner_id = getattr(owner, 'pk', None) if owner else getattr(obj, f'{self.owner_field}_id', None)
        
        # 本人放行
        if owner_id == getattr(user, 'pk', None):
            return True
        
        # 检查跨组访问权限
        user_groups = self.get_user_groups(user)
        owner_user = owner if owner else None
        owner_groups = self.get_user_groups(owner_user) if owner_user else set()
        
        # 选手可以查看教练，教练可以查看选手
        is_user_competitor = GROUP_COMPETITOR in user_groups
        is_user_coach = GROUP_COACH in user_groups
        is_owner_competitor = GROUP_COMPETITOR in owner_groups
        is_owner_coach = GROUP_COACH in owner_groups
        
        return (is_user_competitor and is_owner_coach) or (is_user_coach and is_owner_competitor)
    
    def get_object(self, queryset: Any = None) -> Any:
        """重写 get_object 以添加跨组访问权限检查"""
        obj = super().get_object(queryset)  # type: ignore
        if not self.check_cross_group_access(obj):
            raise Http404
        return obj


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
