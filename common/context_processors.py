# common/context_processors.py
"""
自定义上下文处理器模块
提供一些常用的上下文处理器
在模板中可用：
    {{ site_info.site_name }}
    ...
"""

from django.conf import settings
from django.utils import timezone


def custom_context(request):
    """
    自定义上下文处理器
    """
    site_info = {
        "site_name": getattr(settings, 'SITE_NAME', 'Training Management System'),
        "site_description": getattr(settings, 'SITE_DESCRIPTION', 'A simple training management system.'),
        "site_keywords": getattr(settings, 'SITE_KEYWORDS', 'TMS, Training Management System, Training, Management'),
        "site_author": getattr(settings, 'SITE_AUTHOR', 'hdaojin'),
        "site_copyright": getattr(settings, 'SITE_COPYRIGHT', '2022-{} ITNSA. All rights reserved.'.format(timezone.now().year)),
    }

    context = {
        "site_info": site_info,
    }

    return context
