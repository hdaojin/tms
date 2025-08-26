from django import template
from django.utils.safestring import SafeString
from django.forms.boundfield import BoundField

register = template.Library()


@register.filter(name='rewrite_class')
def rewrite_class(field, css_class):
    """
    为表单字段重写CSS类，覆盖原有类。
    用法： {{ form.field_name|rewrite_class:"css-class-name" }}
    """
    if isinstance(field, BoundField):
        return field.as_widget(attrs={"class": css_class})
    return field


@register.filter(name='add_class')
def add_class(field, css_class):
    """
    为表单字段添加CSS类，保留原有类。
    用法： {{ form.field_name|add_class:"css-class-name" }}
    """
    if isinstance(field, BoundField):
        existing_classes = field.field.widget.attrs.get('class', '')
        if existing_classes:
            new_classes = f"{existing_classes} {css_class}"
        else:
            new_classes = css_class
        return field.as_widget(attrs={"class": new_classes})
    return field


@register.filter(name='add_placeholder')
def add_placeholder(field, placeholder_text):
    """
    为表单字段添加placeholder属性。
    用法： {{ form.field_name|add_placeholder:"Enter your text" }}
    注意：这个过滤器必须在add_class之前使用，因为它需要原始的字段对象
    """
    if isinstance(field, BoundField):
        # 获取现有属性
        attrs = field.field.widget.attrs.copy()
        attrs['placeholder'] = placeholder_text
        return field.as_widget(attrs=attrs)
    return field


@register.filter(name='add_attr')
def add_attr(field, attr):
    """
    为表单字段添加任意属性, 支持两种格式:
    1) key:value -> {{ form.field_name|add_attr:"key:value" }}
    2) boolean -> {{ form.field_name|add_attr:"disabled" }}
    注意：这个过滤器必须在add_class之前使用
    """
    if isinstance(field, BoundField):
        attrs = field.field.widget.attrs.copy()
        if ':' in attr:
            key, value = attr.split(':', 1)
            attrs[key] = value
        else:
            attrs[attr] = True
        return field.as_widget(attrs=attrs)
    return field