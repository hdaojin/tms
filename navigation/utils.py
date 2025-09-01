# navigation/utils.py
"""
导航工具模块
"""

from django.urls import reverse, NoReverseMatch
from django.utils import timezone


def item_resolve_url(item):
    """
    解析菜单项的URL，支持多种指向方式
    优先级：external_url > named_url > flatpage > generic object

    Args:
        item (MenuItem): 菜单项实例

    Returns:
        str: 解析后的URL字符串，如果无法解析则返回'#'
    """
    # 指向方式1：外部链接
    if item.external_url:
        return item.external_url

    # 指向方式2：命名路由
    if item.named_url:
        try:
            url = reverse(item.named_url, kwargs=item.url_kwargs or {})
        except NoReverseMatch:
            return '#'
        # 添加查询参数
        if item.url_query:
            from urllib.parse import urlencode
            query_string = urlencode(item.url_query)
            url = f"{url}?{query_string}"
        return url
    
    # 指向方式3：FlatPage 页面
    if item.flatpage:
        return item.flatpage.get_absolute_url()
    
    # 指向方式4：通用对象
    if item.content_object and hasattr(item.content_object, 'get_absolute_url'):
        try:
            url = item.content_object.get_absolute_url()
            return url
        except Exception:
            return '#'
    
    return '#'


def item_is_visible(request, item):
    """
    判断菜单项是否在当前请求下可见
    1. 检查时间范围
    2. 检查权限

    Args:
        request (HttpRequest): 当前请求对象
        item (MenuItem): 菜单项实例

    Returns:
        bool: 是否可见
    """
    user = getattr(request, 'user', None)
    now = timezone.now()

    # 可见性标志
    if not item.is_visible:
        return False

    # 时间范围检查
    if item.start_at and item.start_at > now:
        return False
    if item.end_at and item.end_at < now:
        return False

    # 权限检查
    if item.required_perms:
        if not user or not user.has_perms(item.required_perms):
            return False

    return True


def mark_active(request_path, items):
    """
    根据当前路径标记 active/open（父级也 open）。
    简单策略：当前 path 以 item.url 开头（或相等）则激活。

    Args:
        request_path (str): 当前请求路径
        item (MenuItem): 菜单项实例

    Returns:
        bool: 是否为活动项
    """
    # 解析每个菜单项的 URL
    for item in items:
        item._url = item_resolve_url(item)


    def is_active(item):
        u = getattr(item, '_url', '') or ''
        if not u.startswith('/'):
            return False
        # 修复：正确处理URL路径匹配
        if request_path == u:
            return True
        # 检查是否是子路径（确保u以/结尾）
        if not u.endswith('/'):
            u += '/'
        return request_path.startswith(u)

    # 递归标记
    for item in items:
        item._active = is_active(item)
        item._open = False

    # 自底向上标记 open，展开父级
    id_map = {item.id: item for item in items}
    for item in items:
        if item._active and item.parent_id:
            p = id_map.get(item.parent_id)
            while p:
                p._open = True
                p = id_map.get(p.parent_id)

    return items