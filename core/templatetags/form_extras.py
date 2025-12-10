# core/templatetags/form_extras.py
from django import template
from django.forms import BoundField, widgets


register = template.Library()

@register.filter
def is_checkbox_input(field: BoundField) -> bool:
    """检查字段是否为复选框"""
    return isinstance(field.field.widget, (widgets.CheckboxInput))

@register.filter
def is_checkbox_multiple(field: BoundField) -> bool:
    """检查字段是否为多选复选框"""
    return isinstance(field.field.widget, (widgets.CheckboxSelectMultiple))

@register.filter
def is_textarea_input(field: BoundField) -> bool:
    """检查字段是否为多行文本输入框"""
    return isinstance(field.field.widget, (widgets.Textarea))