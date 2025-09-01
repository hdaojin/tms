# common/menus_registry.py
"""
自动注册各个应用的菜单项

权限系统说明：
- 菜单项权限通过 'perms' 字段定义为权限列表
- 支持的权限类型：
  1. [] 或 None：公开访问，无需登录
  2. ['is_authenticated']：需要登录
  3. ['is_staff']：需要是管理员
  4. ['is_superuser']：需要是超级管理员
  5. ['app.permission']：需要特定Django权限
  6. 可组合多个权限：['is_authenticated', 'myapp.view_model']

示例：
```python
MENUS = [
    {
        "name": "公开页面",
        "url_name": "pages:about", 
        "perms": [],  # 公开访问
    },
    {
        "name": "用户页面",
        "url_name": "accounts:profile",
        "perms": ["is_authenticated"],  # 需要登录
    },
    {
        "name": "管理页面", 
        "url_name": "admin:index",
        "perms": ["is_staff"],  # 需要管理员权限
    },
    {
        "name": "高级功能",
        "url_name": "advanced:feature",
        "perms": ["is_authenticated", "myapp.advanced_feature"],  # 需要登录+特定权限
    }
]
```
"""

from importlib import import_module
from django.conf import settings
from django.urls import reverse, NoReverseMatch


_REGISTRED_MENUS = []

def autodiscover_menus(manual_menus=None):
    """
    自动发现并导入各个应用的menus模块，同时支持手动指定的MENUS
    
    Args:
        manual_menus (list, optional): 手动指定的菜单项列表，每个元素应该是一个菜单配置字典
                                     如果指定了manual_menus，则不再自动收集app的menus
    """
    global _REGISTRED_MENUS
    if _REGISTRED_MENUS:
        return
    collected = []

    # 如果指定了手动菜单，则只使用手动菜单，不再自动发现
    if manual_menus:
        for menu in manual_menus:
            if isinstance(menu, dict):
                # 为手动菜单添加默认的app_label标识
                menu = {**menu, "__app_label": menu.get("__app_label", "manual")}
                collected.append(menu)
    else:
        # 只有在没有指定手动菜单时，才自动发现各个应用的menus模块
        for app in settings.INSTALLED_APPS:
            try:
                module = import_module(f"{app}.menus")
            except Exception:
                continue

            menus = getattr(module, "MENUS", None)
            if not menus:
                continue
            app_label = app.split('.')[-1]
            for sec in menus:
                sec = {**sec, "__app_label": sec.get("__app_label", app_label)}
                collected.append(sec)
    
    _REGISTRED_MENUS = collected


def _has_perms(user, item):
    """
    检查用户是否有权限查看菜单项
    遵循Django权限系统的逻辑
    """
    perms = item.get('perms', [])
    
    # 如果没有设置权限要求，认为是公开访问
    if not perms:
        return True
    
    # 如果用户未认证，只能访问公开内容
    if not user or not user.is_authenticated:
        return False
    
    # 检查特殊权限
    if 'is_authenticated' in perms:
        if not user.is_authenticated:
            return False
    
    if 'is_staff' in perms:
        if not user.is_staff:
            return False
            
    if 'is_superuser' in perms:
        if not user.is_superuser:
            return False
    
    # 检查Django权限（app.permission格式）
    django_perms = [p for p in perms if '.' in p and p not in ['is_authenticated', 'is_staff', 'is_superuser']]
    if django_perms:
        if not user.has_perms(django_perms):
            return False
    
    return True


def _current_app_label(request):
    """
    从 resolver_match 推断当前 app：
    1) app_names（Django 自带 app_name 链）
    2) namespaces（实例/包含命名空间）
    3) view_name 前缀（'ns:view' → 'ns'）

    """
    rm = getattr(request, 'resolver_match', None)
    if not rm:
        return None
    if getattr(rm, 'app_names', None):
        return rm.app_names[-1]
    if getattr(rm, 'namespaces', None):
        if rm.namespaces:
            return rm.namespaces[0]
    if rm.view_name and ':' in rm.view_name:
        return rm.view_name.split(':', 1)[0]
    return None


def _build_menu_items(request, menu_items):
    """
    通用的菜单项构建函数
    """
    user = getattr(request, 'user', None)
    current_view = getattr(request, 'resolver_match', None)
    current_url_name = current_view.view_name if current_view else None
    
    items = []
    for item in menu_items:
        # 权限检查
        if not _has_perms(user, item):
            continue
            
        url_name = item.get('url_name')
        url_kwargs = item.get('url_kwargs', {})
        try:
            url = reverse(url_name, kwargs=url_kwargs) if url_name else item.get('url', '#')
        except NoReverseMatch:
            url = '#'
            
        menu_item = {
            "name": item.get('name'),
            "url": url,
            "active": (url_name == current_url_name) if url_name else (url == request.path),
        }
        
        # 侧边栏菜单可能需要图标
        if item.get('icon'):
            menu_item["icon"] = item.get('icon')
            
        items.append(menu_item)
    
    return items


def build_menus(request, fix_app=None, manual_menus=None):
    """
    构建菜单
    """
    autodiscover_menus(manual_menus=manual_menus)

    if not fix_app:
        current_app = _current_app_label(request)
    else:
        current_app = fix_app

    custom_menus = []
    for section in _REGISTRED_MENUS:
        # 菜单显示逻辑：
        # 1. scope='global' 的菜单全局显示
        # 2. manual 菜单默认全局显示
        # 3. 当前 app 的菜单显示
        scope = section.get('scope')
        app_label = section.get('__app_label')
        
        should_display = (
            scope == 'global' or 
            app_label == 'manual' or 
            app_label == current_app
        )
        
        if not should_display:
            continue

        items = _build_menu_items(request, section.get('items', []))
        
        if items:
            custom_menus.append({
                "section": section.get('section'),
                "items": items,
            })
    return custom_menus
