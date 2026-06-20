from __future__ import annotations

from django import template

from core.navigation import (
    get_section_items,
    get_theme_choices,
    get_visible_sections,
    resolve_current_section,
)

register = template.Library()


@register.simple_tag
def enabled_themes() -> list[str]:
    return get_theme_choices()


@register.inclusion_tag("partials/sidebar.html", takes_context=True)
def render_section_menu(context, section_slug: str):
    request = context.get("request")
    if not request:
        return {"items": []}
    return {"items": get_section_items(section_slug, request.user, request=request)}


@register.inclusion_tag("partials/sidebar.html", takes_context=True)
def render_section_menu_auto(context):
    request = context.get("request")
    if not request:
        return {"items": []}
    section_slug = resolve_current_section(request)
    items = get_section_items(section_slug, request.user, request=request) if section_slug else []
    return {"items": items}


@register.inclusion_tag("partials/sidebar.html", takes_context=True)
def render_menu(context, menu_slug: str):
    request = context.get("request")
    if not request:
        return {"items": []}
    return {"items": get_section_items(menu_slug, request.user, request=request)}


@register.inclusion_tag("partials/header_nav.html", takes_context=True)
def render_sections_nav(context):
    request = context.get("request")
    if not request:
        return {"sections": []}
    return {
        "sections": get_visible_sections(
            request.user,
            request=request,
            layout_key="header",
        )
    }


@register.inclusion_tag("partials/mobile_nav.html", takes_context=True)
def render_mobile_navigation(context):
    request = context.get("request")
    if not request:
        return {"sections": [], "site_info": context.get("site_info")}
    return {
        "sections": get_visible_sections(request.user, request=request, include_items=True),
        "site_info": context.get("site_info"),
    }


@register.inclusion_tag("partials/section_cards.html", takes_context=True)
def render_sections_cards(context):
    request = context.get("request")
    if not request:
        return {"sections": []}
    return {
        "sections": get_visible_sections(
            request.user,
            request=request,
            layout_key="dashboard",
        )
    }
