from django.conf import settings
from .menus import get_main_menu_items
from accounts.menus import get_user_menu_items
from pages.menus import page_menu_items
from articles.menus import article_menu_items
from traininglogs.menus import get_training_log_menu_items
from meeting.menus import  get_meeting_menu_items


def custom_context(request):
    """
    自定义上下文处理器
    """
    site_info = {
        "my_site_name": settings.MY_SITE_NAME,
    }

    custom_menus = {
        "main_menu": get_main_menu_items(request.user),
        "user_menu_items": get_user_menu_items(request.user),
        "training_log_menu_items": get_training_log_menu_items(request.user),
        "page_menu_items": page_menu_items,
        "article_menu_items": article_menu_items,
        "meeting_menu_items": get_meeting_menu_items(request.user)
    }

    template_layout = {
        "header": True,
        "main": True,
        "left_sidebar": True,
        "right_sidebar": False,
        "footer": True,
    }

    context = {
        "site_info": site_info,
        "custom_menus": custom_menus,
        "template_layout": template_layout,
    }

    return context
