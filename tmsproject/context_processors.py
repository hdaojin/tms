from django.conf import settings
from .menus import main_menu_items
from accounts.menus import get_user_menu_items
from pages.menus import page_menu_items
from articles.menus import article_menu_items
from traininglogs.menus import get_training_log_menu_items


def custom_context(request):
    return {
        "my_site_name": settings.MY_SITE_NAME,
        "main_menu_items": main_menu_items,
        "user_menu_items": get_user_menu_items(request.user),
        "training_log_menu_items": get_training_log_menu_items(request.user),
        "page_menu_items": page_menu_items,
        "article_menu_items": article_menu_items,
    }
