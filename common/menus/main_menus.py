# common/main_menus.py
"""
定义网站的主菜单项
"""

# 主菜单项
MENUS = [
    {
        "section": None,  # 主菜单不显示section标题
        "scope": None,  # 主菜单不区分作用域
        "position": "header",  # 主菜单显示在header
        "items": [
            {
                "name": "首页",
                "url": "/",
                "perms": ["is_authenticated"],
            },
            {
                "name": "训练",
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
                "url": "/about/",
                "perms": [],  # 公开访问，无权限要求
            },
        ],
    }
]
