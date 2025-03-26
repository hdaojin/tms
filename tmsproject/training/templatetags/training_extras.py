from django import template

register = template.Library()

@register.filter
def endswith(value, arg):
    """检查值是否以指定参数结尾"""
    return value.endswith(arg)
