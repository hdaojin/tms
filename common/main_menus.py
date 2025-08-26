# common/main_menus.py
"""
定义网站的主菜单项
"""

from django.urls import reverse

# 主菜单项
MENUS = [
    {
        "name": "首页",
        "url_name": "pages:homepage",
        "perms": ["is_authenticated"],
    },
    {
        "name": "日志",
        "url_name": "traininglogs:list_training_logs",
        "perms": ["is_authenticated"],
    },
    {
        "name": "会议",
        "url_name": "meeting:meeting_list",
        "perms": ["is_authenticated"],
    },
    {
        "name": "通知",
        "url_name": "notices:notice_list",
        "perms": ["is_authenticated"],
    },
    {
        "name": "关于",
        "url": reverse("pages:page_detail", kwargs={"slug": "about"}),
        "perms": [],  # 公开访问，无权限要求
    },
]