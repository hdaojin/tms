from django.conf import settings
from django.urls import reverse 


def get_main_menu_items():
    main_menu_items = [
        {
            "name": "首页",
            "url": "/",
        },
        {
            "name": "教学笔记",
            "url": "#",
        },
        {
            "name": "训练日志",
            "url": reverse("traininglogs:list_training_logs"),
        },
        {
            "name": "文章",
            "url": reverse("articles:list"),
        },
        {
            "name": "关于我们",
            "url": reverse("pages:page_detail", kwargs={"slug": "about"}),
        },
    ]
    return main_menu_items


def custom_context(request):
    return {
        "my_site_name": settings.MY_SITE_NAME,
        "main_menu_items": get_main_menu_items(),
    }
