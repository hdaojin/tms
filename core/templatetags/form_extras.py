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

@register.filter
def is_file_input(field: BoundField) -> bool:
    """检查字段是否为文件上传输入框"""
    return isinstance(field.field.widget, (widgets.FileInput, widgets.ClearableFileInput))

@register.filter
def is_multiple_file(field: BoundField) -> bool:
    """检查文件字段是否支持多文件上传"""
    widget = field.field.widget
    return getattr(widget, 'allow_multiple_selected', False)

@register.filter
def get_accept_types(field: BoundField) -> str:
    """获取文件字段的 accept 属性"""
    widget = field.field.widget
    return widget.attrs.get('accept', '')