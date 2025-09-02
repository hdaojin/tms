# navigation/templatetags/nav_tags.py

from django import template
from ..services import get_menu_tree


register = template.Library()


@register.inclusion_tag('navigation/menu.html', takes_context=True)
def render_menu(context, slug_or_location):
    """
    渲染指定菜单的模板标签

    用法:
        {% load nav_tags %}
        {% render_menu 'header' %}
    Args:
        context (dict): 模板上下文
        slug_or_location (str): 菜单的 slug 或 位置标识符

    Returns:
        dict: 包含菜单项树形结构的上下文字典
    """
    request = context['request']
    menu, tree = get_menu_tree(request, slug_or_location)
    return {
        'menu': menu,
        'tree': tree
    }


@register.inclusion_tag('navigation/sidebar_menu.html', takes_context=True)
def render_sidebar_menu(context, slug_or_location):
    """
    渲染侧边栏菜单的模板标签

    用法:
        {% load nav_tags %}
        {% render_sidebar_menu 'sidebar' %}
        {% render_sidebar_menu 'follow' %}

    Args:
        context (dict): 模板上下文
        slug_or_location (str): 菜单的 slug 或 位置标识符

    Returns:
        dict: 包含菜单项树形结构的上下文字典
    """
    request = context['request']

    if slug_or_location == 'follow':
        slug_or_location = request.resolver_match.app_name

    menu, tree = get_menu_tree(request, slug_or_location)

    return {
        'menu': menu,
        'tree': tree
    }