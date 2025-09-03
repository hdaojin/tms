# navigation/services.py
from django.core.cache import cache
from django.conf import settings
from .models import Menu, MenuItem
from .utils import item_resolve_url, item_time_window_ok, user_meets_menu_requirements, mark_active

CACHE_TIMEOUT = getattr(settings, 'CACHE_TIMEOUT', 300)  # 5 min

def _fetch_menu(slug_or_location: str):
    """根据 slug 或 location 获取活动菜单"""
    try:
        return Menu.objects.get(slug=slug_or_location, is_active=True)
    except Menu.DoesNotExist:
        return Menu.objects.filter(is_active=True, locations__contains=slug_or_location).first()

def get_menu_tree(request, slug_or_location):
    """获取指定菜单的树形结构，包含权限和可见性过滤"""
    menu = _fetch_menu(slug_or_location)
    if not menu:
        return None, []

    cache_key = f"nav.m2m_items.{menu.id}"   # type: ignore
    items = cache.get(cache_key)
    if items is None:
        items = list(
            MenuItem.objects.filter(menus=menu)
            .select_related("parent", "flatpage")
            .prefetch_related("permissions")
            .only(
                "id","parent_id","name","icon","order",
                "is_visible","start_at","end_at",
                "perm_match_all","login_required","is_group_header",
                "named_url","url_kwargs","url_query","flatpage_id","external_url",
                "target_blank","css_classes","htmx_attrs",
            )
        )
        cache.set(cache_key, items, CACHE_TIMEOUT)

    # 过滤
    visible = [it for it in items if item_time_window_ok(it) and user_meets_menu_requirements(request.user, it)]
    visible = mark_active(request.path, visible)

    # 构树（仅挂接可见父）
    visible_ids = {it.id for it in visible}   # type: ignore
    by_parent = {}
    for it in visible:
        pid = it.parent_id if (it.parent_id in visible_ids) else None  # type: ignore
        by_parent.setdefault(pid, []).append(it)
    for k in by_parent:
        by_parent[k].sort(key=lambda x: (x.order, x.id))

    def build(pid=None):
        res = []
        for it in by_parent.get(pid, []):
            res.append({
                "id": it.id,
                "name": it.name,
                "icon": it.icon,
                "url": item_resolve_url(it),
                "active": getattr(it, "_active", False),
                "open": getattr(it, "_open", False),
                "css_classes": it.css_classes,
                "target_blank": it.target_blank,
                "htmx": it.htmx_attrs or {},
                "is_group_header": it.is_group_header,
                "children": build(it.id),
            })
        return res

    return menu, build(None)
