# common/templatetags/menu_tags.py
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(is_safe=True)
def link_attrs(item) -> str:
    """
    生成菜单项的链接属性字符串
    Args:
        item (dict): 菜单项字典
    Returns:
        str: 链接属性字符串
    """
    attrs = []
    if item.get("target_blank"):
        attrs.append('target="_blank" rel="noopener"')
    htmx_attrs = item.get("htmx_attrs", {})
    for k, v in htmx_attrs.items():
        attrs.append(f'{k}="{v}"')
    return " ".join(attrs)


@register.filter(is_safe=True)
def css_classes(item) -> str:
    """
    获取菜单项的 CSS 类字符串
    Args:
        item (dict): 菜单项字典
    Returns:
        str: CSS 类字符串
    """
    return item.get("css_classes", "") or ""


@register.filter(name="icon", is_safe=True)
def render_icon(value, size: str = "6", color: str = "text-primary") -> str:
    """渲染图标:
    用法:
        {{ item|icon }}                     # 从字典 item['icon'] 读取
        {{ item|icon:'5' }}                 # 指定 size
        {{ item|icon:'5 text-red-500' }}    # 指定 size 和 color
        {{ 'icon-[tabler--user]'|icon }}    # 直接传类名
    """
    if not value:
        return ""
    # value 可能是 dict（整条 item）或直接的类名字符串
    icon_class = value.get("icon") if isinstance(value, dict) else value
    if not icon_class:
        return ""
    return mark_safe(f'<i class="{icon_class} size-{size} {color}"></i>')