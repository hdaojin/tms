# navigation/utils.py
from urllib.parse import urlencode
from django.urls import reverse, NoReverseMatch
from django.utils import timezone

def item_resolve_url(item):
    """
    解析菜单项的最终URL
    Args:
        item (MenuItem): 菜单项实例
    Returns:
        str: 解析后的URL
    """
    if item.is_group_header:
        return "#"
    if item.external_url:
        return item.external_url
    if item.named_url:
        try:
            url = reverse(item.named_url, kwargs=item.url_kwargs or {})
        except NoReverseMatch:
            return "#"
        if item.url_query:
            url += ("?" + urlencode(item.url_query))
        return url
    if item.flatpage:
        return item.flatpage.get_absolute_url()
    return "#"

def item_time_window_ok(item):
    """
    检查菜单项的时间窗口和可见性
    Args:
        item (MenuItem): 菜单项实例
    Returns:
        bool: 是否在时间窗口内且可见
    """
    now = timezone.now()
    if item.start_at and now < item.start_at:
        return False
    if item.end_at and now > item.end_at:
        return False
    return item.is_visible

def user_meets_menu_requirements(user, item) -> bool:
    """
    检查用户是否满足菜单项的权限和登录要求
    Args:
        user (User): 用户实例
        item (MenuItem): 菜单项实例
    Returns:
        bool: 用户是否满足要求
    """
    if item.login_required and not user.is_authenticated:
        return False
    # 直接使用 M2M 权限
    try:
        perms = [f"{p.content_type.app_label}.{p.codename}" for p in item.permissions.all()]
    except Exception:
        perms = []
    if not perms:
        return True
    if not user.is_authenticated:
        return False
    if item.perm_match_all:
        return all(user.has_perm(p) for p in perms)
    return any(user.has_perm(p) for p in perms)

def mark_active(request_path, items):
    """
    标记菜单项的 active 和 open 状态
    Args:
        request_path (str): 当前请求路径
        items (list): 菜单项列表
    Returns:
        list: 标记后的菜单项列表
    """
    for it in items:
        it._url = item_resolve_url(it)

    def is_active(it):
        u = getattr(it, "_url", "") or ""
        if not u.startswith("/"):   # 外链/分组标题不参与“激活”匹配
            return False
        return request_path == u or request_path.startswith(u.rstrip("/") + "/")

    id_map = {it.id: it for it in items}
    for it in items:
        it._active = is_active(it)
        it._open = False

    # 自底向上展开父级
    for it in items:
        if it._active and it.parent_id:
            p = id_map.get(it.parent_id)
            while p:
                p._open = True
                p = id_map.get(p.parent_id)
    return items
