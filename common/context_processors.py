# common/context_processors.py
"""
自定义上下文处理器模块
提供一些常用的上下文处理器
在模板中可用：
    {{ site_info.site_name }}
    ...
"""

from .models import SiteConfig


def custom_context(request):
    """
    自定义上下文处理器, 在所有模板中注入站点配置信息
    """
    site_info = SiteConfig.get_solo()

    context = {
        "site_info": site_info,
    }

    return context
