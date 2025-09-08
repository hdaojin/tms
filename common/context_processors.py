# common/context_processors.py
"""
自定义上下文处理器模块
提供一些常用的上下文处理器
在模板中可用：
    {{ site_info.site_name }}
    ...
"""

from django.conf import settings


def custom_context(request):
    """
    自定义上下文处理器
    """
    site_info = getattr(settings, 'SITE_INFO', {})

    context = {
        "site_info": site_info,
    }

    return context
