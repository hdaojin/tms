# common/templatetags/menus.py
from django import template

from common.menus_registry import build_siderbar_menu, build_main_menu


register = template.Library()


@register.simple_tag(takes_context=True)
def get_sidebar_menu(context):
    request = context['request']
    sidebar_menu = build_siderbar_menu(request)
    return sidebar_menu


@register.simple_tag(takes_context=True)
def get_main_menu(context):
    request = context['request']
    main_menu = build_main_menu(request)
    return main_menu


@register.simple_tag(takes_context=True)
def get_user_menu(context):
    request = context['request']
    user_menu = build_siderbar_menu(request, current_app='accounts')
    return user_menu