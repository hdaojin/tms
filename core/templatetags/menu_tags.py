# core/templatetags/menu_tags.py
from django import template

from core.utils.menus import (
    get_all_menus,
    get_layout_sections,
    get_menu_by_slug,
    get_section_menu,
    get_sections,
)

register = template.Library()


def _first_item_url(items):
    for item in items:
        if item.resolved_url and item.resolved_url != "#":
            return item.resolved_url
        if item.children:
            child_url = _first_item_url(item.children)
            if child_url:
                return child_url
    return None


def _resolve_section_slug_for_request(request):
    match = getattr(request, "resolver_match", None)
    app_name = getattr(match, "app_name", None)
    # 优先：按 section.include_menus 直接匹配 app_name（兼容旧配置）
    if app_name:
        for section in get_sections():
            include = section.get("include") or section.get("include_menus", []) or []
            if app_name in include:
                return section.get("section")

    # 次级：按菜单定义的 app_name -> menu_slug，再找包含该 menu_slug 的 section
    if app_name:
        app_menus = get_all_menus()
        for menu_slug, menu_def in app_menus.items():
            if menu_def.get("app_name") == app_name:
                for section in get_sections():
                    include = section.get("include") or section.get("include_menus", []) or []
                    if menu_slug in include:
                        return section.get("section")

    # 平台内置 flatpages 映射到 about 区域（兼容 app_name 差异）
    flatpage_app_names = {"flatpage", "flatpages", "django.contrib.flatpages"}
    if app_name in flatpage_app_names:
        for section in get_sections():
            include = section.get("include") or section.get("include_menus", []) or []
            if "about" in include:
                return section.get("section")

    # 路径前缀兜底：/about/ 归入 about 区域
    path = getattr(request, "path", "") or ""
    if path.startswith("/about/"):
        for section in get_sections():
            include = section.get("include") or section.get("include_menus", []) or []
            if "about" in include:
                return section.get("section")

    # fallback: 匹配 flatpage 等无 app_name 的菜单片段
    for section in get_sections():
        include = section.get("include") or section.get("include_menus", []) or []
        if "flatpage" in include:
            return section.get("section")
    return None


@register.inclusion_tag("core/partials/sidebar_menu.html", takes_context=True)
def render_section_menu(context, section_slug: str):
    """根据主菜单节点（section）渲染侧边栏。"""
    request = context.get("request")
    if not request:
        return {"items": []}
    items = get_section_menu(section_slug, request.user, request=request)
    return {"items": items}


@register.inclusion_tag("core/partials/sidebar_menu.html", takes_context=True)
def render_section_menu_auto(context):
    """自动根据当前 app 判断所属 section 并渲染侧边栏。"""
    request = context.get("request")
    if not request:
        return {"items": []}
    section_slug = _resolve_section_slug_for_request(request)
    items = get_section_menu(section_slug, request.user, request=request) if section_slug else []
    return {"items": items}


@register.inclusion_tag("core/partials/sidebar_menu.html", takes_context=True)
def render_menu(context, menu_slug: str):
    """
    如有需要，可以直接按 menu_slug 渲染单个菜单片段。
    例如：{% render_menu "accounts" %}
    """
    request = context.get("request")
    if not request:
        return {"items": []}
    items = get_menu_by_slug(menu_slug, request.user)
    return {"items": items}


def _filter_sections(slug_string: str | None, default_key: str | None = None) -> list[dict]:
    all_sections = get_sections()
    desired: list[str] = []
    if slug_string:
        desired = [s.strip() for s in slug_string.split(",") if s.strip()]
    elif default_key:
        desired = get_layout_sections(default_key)
    if not desired:
        return all_sections
    lookup = {s.get("section"): s for s in all_sections}
    return [lookup[slug] for slug in desired if slug in lookup]


@register.inclusion_tag("core/partials/sections_nav.html", takes_context=True)
def render_sections_nav(context, slugs: str | None = None):
    """顶部导航：可按逗号分隔指定，或从 layout.yml.header_sections 读取。"""
    request = context.get("request")
    if not request:
        return {"sections": []}
    user = request.user
    sections = []
    for section in _filter_sections(slugs, default_key="header_menu"):
        login_flag = section.get("login_required")
        login_needed = True if login_flag is None else bool(login_flag)
        if (login_needed or section.get("required_perms")) and not user.is_authenticated:
            continue
        slug = section.get("section")
        items = get_section_menu(slug, user, request=request)  #type: ignore
        if not items:
            continue
        url = _first_item_url(items) or "#"
        active = any(item.active for item in items)
        sections.append({
            "slug": slug,
            "label": section.get("label", slug),
            "icon": section.get("icon"),
            "url": url,
            "active": active,
        })
    return {"sections": sections}


@register.inclusion_tag("core/partials/sections_cards.html", takes_context=True)
def render_sections_cards(context, slugs: str | None = None):
    """账户首页卡片：可按逗号分隔指定，或从 layout.yml.account_home_sections 读取。"""
    request = context.get("request")
    if not request:
        return {"sections": []}
    user = request.user
    sections = []
    for section in _filter_sections(slugs, default_key="dashboard_home"):
        login_flag = section.get("login_required")
        login_needed = True if login_flag is None else bool(login_flag)
        if (login_needed or section.get("required_perms")) and not user.is_authenticated:
            continue
        slug = section.get("section")
        items = get_section_menu(slug, user, request=request)  # type: ignore
        if not items:
            continue
        url = _first_item_url(items) or "#"
        sections.append({
            "slug": slug,
            "label": section.get("label", slug),
            "icon": section.get("icon"),
            "description": section.get("description"),
            "url": url,
            "count": len(items),
        })
    return {"sections": sections}
