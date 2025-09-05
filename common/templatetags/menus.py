# common/templatetags/menus.py
from django import template
from common.utils.menus_parse import (
    build_menu_tree_for_app,
    build_menu_tree_for_flatpages,
    build_menu_tree_for_header,
)


register = template.Library()


# 渲染侧边栏垂直显示的指定应用菜单
@register.inclusion_tag("components/menu_vertical.html", takes_context=True)
def render_app_menu(context, app_name: str) -> dict:
    """
    渲染指定应用的菜单模板标签

    用法:
        {% load menus %}
        {% render_app_menu 'app_name' %}
    Args:
        context (dict): 模板上下文
        app_name (str): 应用名称

    Returns:
        dict: 包含菜单项树形结构的上下文字典
    """
    request = context["request"]
    menus_tree = build_menu_tree_for_app(request, app_name)
    return {"menus_tree": menus_tree}

# 渲染侧边栏垂直显示的当前应用菜单
@register.inclusion_tag("components/menu_vertical.html", takes_context=True)
def render_current_app_menu(context) -> dict:
    """
    渲染当前请求应用（通过resolver_match.app_name）的菜单模板标签

    用法:
        {% load menus %}
        {% render_current_app_menu %}
    Args:
        context (dict): 模板上下文
    Returns:
        dict: 包含菜单项树形结构的上下文字典
    """
    request = context["request"]
    # app_name = getattr(getattr(request, 'resolver_match', None), 'app_name', None)
    app_name = getattr(request.resolver_match, 'app_name', None)

    if not app_name:
        return {"menus_tree": []}

    menus_tree = build_menu_tree_for_app(request, app_name)

    return {"menus_tree": menus_tree}

# 渲染flatpages菜单
@register.inclusion_tag("components/menu_vertical.html", takes_context=True)
def render_flatpages_menu(context) -> dict:
    request = context["request"]
    menus_tree = build_menu_tree_for_flatpages(request)
    return {"menus_tree": menus_tree}


# 渲染顶部菜单, 横向显示
@register.inclusion_tag("components/menu_horizontal.html", takes_context=True)
def render_header_menu(context) -> dict:
    request = context["request"]
    menus_tree = build_menu_tree_for_header(request)
    return {"menus_tree": menus_tree}