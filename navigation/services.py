# navigation/services.py
"""
导航服务模块
"""

from django.core.cache import cache

from .models import Menu, MenuItem
from .utils import item_is_visible, item_resolve_url, mark_active


CACHE_TIMEOUT = 300  # 缓存时间，单位秒

def get_menu_tree(request, slug_or_location):
    """
    获取指定菜单的树形结构，应用权限和可见性过滤，并标记当前活动项

    Args:
        request (HttpRequest): 当前请求对象
        slug_or_location (str): 菜单的 slug 或 位置标识符

    Returns:
        list: 经过过滤和处理的菜单项树形结构
    """

    # 找菜单
    try:
        menu = Menu.objects.get(is_active=True, slug=slug_or_location)
    except Menu.DoesNotExist:
        # 对于MultiSelectField，使用contains查询
        menu = Menu.objects.filter(is_active=True, locations__contains=slug_or_location).first()
    if not menu:
        return None, []
    
    # 缓存键
    cache_key = f"nav.items.{menu.id}"   # type: ignore
    items = cache.get(cache_key)
    if items is None:
        items = list(MenuItem.objects.filter(menus=menu).select_related('parent', 'flatpage', 'content_type'))
        cache.set(cache_key, items, CACHE_TIMEOUT)

    # 过滤可见项
    visible = [item for item in items if item_is_visible(request, item)]

    # 标记 active/open
    visible = mark_active(request.path, visible)

    # 构建树形结构
    by_parent = {}
    for item in visible:
        by_parent.setdefault(item.parent_id, []).append(item)   # type: ignore
    for k in by_parent:
        by_parent[k].sort(key=lambda x: (x.order, x.name))

    def build_tree(parent_id=None):
        subtree = []
        for item in by_parent.get(parent_id, []):
            node = {
                "id": item.id,
                "name": item.name,
                "icon": item.icon,
                "url": item_resolve_url(item),
                "active": getattr(item, '_active', False),
                "open": getattr(item, '_open', False),
                "css_classes": item.css_classes,
                "target_blank": item.target_blank,
                "htmx_attrs": item.htmx_attrs or {},
                "children": build_tree(item.id)
            }
            subtree.append(node)
        return subtree

    tree = build_tree(None)
    return menu, tree