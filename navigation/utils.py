# navigation/utils.py
"""
导航工具模块
"""

from functools import lru_cache
from typing import List, Tuple, Iterable

from django.urls import reverse, NoReverseMatch, get_resolver, URLPattern, URLResolver
from django.utils import timezone


def item_resolve_url(item):
    """
    解析菜单项的URL，支持多种指向方式
    优先级： named_url > flatpage > external_url

    Args:
        item (MenuItem): 菜单项实例

    Returns:
        str: 解析后的URL字符串，如果无法解析则返回'#'
    """
    # 指向方式1：命名路由
    if item.named_url:
        try:
            url = reverse(item.named_url, kwargs=item.url_kwargs or {})
        except NoReverseMatch:
            return "#"
        # 添加查询参数
        if item.url_query:
            from urllib.parse import urlencode

            query_string = urlencode(item.url_query)
            url = f"{url}?{query_string}"
        return url

    # 指向方式2：FlatPage 页面
    if item.flatpage:
        return item.flatpage.get_absolute_url()

    # 指向方式3：外部链接
    if item.external_url:
        return item.external_url

    return "#"


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
    user = getattr(request, "user", None)
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
        # 如果没有用户对象，则拒绝所有需要权限的项目
        if not user:
            return False

        # 检查每个所需权限
        for perm in item.required_perms:
            # 特殊处理：检查用户是否已登录
            if perm == "is_authenticated":
                if not user.is_authenticated:
                    return False
            # 特殊处理：检查用户是否为管理员
            elif perm == "is_staff":
                if not user.is_staff:
                    return False
            elif perm == "is_superuser":
                if not user.is_superuser:
                    return False
            # 标准权限检查（格式：app_label.permission_codename）
            else:
                if not user.has_perm(perm):
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
        u = getattr(item, "_url", "") or ""
        if not u.startswith("/"):
            return False
        # 修复：正确处理URL路径匹配
        if request_path == u:
            return True
        # 检查是否是子路径（确保u以/结尾）
        if not u.endswith("/"):
            u += "/"
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


"""navigation.url_discovery
自动发现项目中（排除admin）的命名URL以供菜单使用。

提供函数 get_named_url_choices() 返回适合用作 ChoiceField 的列表。
"""


def _iter_urlpatterns(patterns: Iterable, namespace_prefix: str = ""):
    """递归遍历 URLPattern / URLResolver，生成 (full_name, pattern_str)。"""
    for p in patterns:
        if isinstance(p, URLResolver):  # include(...) 的情况
            ns = p.namespace
            new_prefix = namespace_prefix
            if ns:
                new_prefix = (
                    f"{namespace_prefix}{ns}:" if namespace_prefix else f"{ns}:"
                )
            yield from _iter_urlpatterns(p.url_patterns, new_prefix)
        elif isinstance(p, URLPattern):
            if p.name:  # 只收集有 name 的
                full_name = f"{namespace_prefix}{p.name}"
                # 排除 admin 相关
                if full_name.startswith("admin"):
                    continue
                # pattern 展示
                pattern_str = str(p.pattern)
                yield full_name, pattern_str


@lru_cache(maxsize=1)
def get_named_url_choices() -> List[Tuple[str, str]]:
    """返回[(value, display), ...] 形式的可选命名URL列表。

    使用 lru_cache 缓存一次结果；如需刷新可调用 get_named_url_choices.cache_clear()。
    """
    resolver = get_resolver()
    items = []
    for name, pattern_str in _iter_urlpatterns(resolver.url_patterns):
        display = f"{name} ({pattern_str})"
        items.append((name, display))
    # 排序：按名称
    items.sort(key=lambda x: x[0])
    return items


def refresh_named_url_choices():
    """清除缓存以便重新发现（如动态变更urls后）。"""
    get_named_url_choices.cache_clear()  # type: ignore


# __all__ = [
#     "get_named_url_choices",
#     "refresh_named_url_choices",
# ]
