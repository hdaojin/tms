# core/templatetags/form_extras.py
from django import template
from django.forms import BoundField, widgets
from pathlib import PurePosixPath


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
def is_radio_select(field: BoundField) -> bool:
    """检查字段是否为单选框组"""
    return isinstance(field.field.widget, (widgets.RadioSelect))

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


@register.filter
def get_widget_attr(field: BoundField, name: str) -> str:
    """获取文件控件的自定义属性，供公共表单组件转发配置。"""
    return str(field.field.widget.attrs.get(name, ''))


@register.filter
def file_upload_describedby(field: BoundField) -> str:
    """组合上传组件的静态说明、帮助文本和动态错误关联。"""
    widget_value = str(field.field.widget.attrs.get('aria-describedby', ''))
    ids = widget_value.split()
    ids.extend(
        [
            f'{field.id_for_label}_helptext',
            f'{field.id_for_label}_paste_hint',
        ]
    )
    if field.errors:
        ids.append(f'{field.id_for_label}_error')
    return ' '.join(dict.fromkeys(ids))


@register.filter
def filename(file_path: str) -> str:
    """从文件路径中提取文件名（不含路径）"""
    if not file_path:
        return ''
    return PurePosixPath(str(file_path)).name


@register.filter
def filesize_display(size_bytes: int) -> str:
    """将文件大小（字节）转换为人类可读格式"""
    if not size_bytes:
        return ''
    
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
