"""统一页面面包屑；业务父级由调用方在权限边界内显式提供。"""

from dataclasses import dataclass, replace

from django.contrib.auth.models import AnonymousUser
from django.urls import NoReverseMatch, reverse

from core.navigation import get_section_items, get_sections, resolve_current_section


@dataclass(frozen=True, slots=True)
class Breadcrumb:
    label: str
    url: str | None = None
    icon_class: str = ""


def breadcrumb_link(label, url_name, *, args=None, kwargs=None):
    """延迟到请求时反解；缺失路由降级为文本。调用方负责权限判断。"""
    try:
        url = reverse(url_name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        url = None
    return Breadcrumb(label, url)


def build_breadcrumbs(request, title, parents=()):
    if not title:
        return []
    home = breadcrumb_link("首页", "home")
    crumbs = [replace(home, icon_class="icon-[tabler--home]")]
    if request is not None:
        section_key = resolve_current_section(request)
        user = getattr(request, "user", AnonymousUser())
        section = next((item for item in get_sections() if item.get("key") == section_key), None)
        items = get_section_items(section_key, user) if section else []
        if items and (not section.get("login_required", True) or user.is_authenticated):
            url = next((item.resolved_url for item in items if item.resolved_url != "#"), None)
            crumbs.append(Breadcrumb(section["label"], url))
    crumbs.extend(parents)
    crumbs.append(Breadcrumb(str(title)))
    result = []
    for crumb in crumbs:
        if not crumb.label:
            continue
        try:
            url = str(crumb.url) if crumb.url else None
        except NoReverseMatch:
            url = None
        crumb = replace(crumb, label=str(crumb.label), url=url)
        if result and result[-1].label == crumb.label:
            previous = result.pop()
            crumb = replace(crumb, icon_class=previous.icon_class or crumb.icon_class)
        result.append(crumb)
    result[-1] = replace(result[-1], url=None)
    return result
