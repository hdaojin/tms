# common/context_processors.py
"""
自定义上下文处理器模块
提供一些常用的上下文处理器
在模板中可用：
    {{ site_info.my_site_name }}
    ...
"""

from django.conf import settings


def custom_context(request):
    """
    自定义上下文处理器
    """
    site_info = {
        "my_site_name": getattr(settings, 'MY_SITE_NAME', 'Training Management System'),
        "my_site_description": getattr(settings, 'MY_SITE_DESCRIPTION', 'A simple training management system.'),
        "my_site_author": getattr(settings, 'MY_SITE_AUTHOR', 'hdaojin'),
    }

    context = {
        "site_info": site_info,
    }

    return context
