# common/templatetags/menus.py
from django import template

from common.utils.menus_registry import build_menus
from common.menus.main_menus import MENUS as MAIN_MENUS
from common.menus.flatpage_menus import MENUS as FLATPAGES_MENUS

register = template.Library()


@register.simple_tag(takes_context=True)
def get_sidebar_menus(context):
    request = context['request']
    sidebar_menus = build_menus(request)
    return sidebar_menus


@register.simple_tag(takes_context=True)
def get_main_menus(context):
    request = context['request']
    main_menus = build_menus(request, manual_menus=MAIN_MENUS)
    return main_menus


@register.simple_tag(takes_context=True)
def get_user_menus(context):
    request = context['request']
    user_menus = build_menus(request, fix_app='accounts')
    return user_menus

@register.simple_tag(takes_context=True)
def get_flatpage_menus(context):
    request = context['request']
    flatpage_menus = build_menus(request, manual_menus=FLATPAGES_MENUS)
    return flatpage_menus