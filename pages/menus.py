# pages/menus.py
"""
页面菜单项注册
"""

MENUS = [
    {
        "section": "关于",
        "items": [
            {
                "name": "关于本站",
                "url_name": "pages:page_detail",
                "url_kwargs": {"slug": "about"},
                "icon": "icon-[tabler--info-circle]",
                "perms": [],  # 公开访问，无权限要求
            },
            {
                "name": "关于作者",
                "url_name": "pages:page_detail",
                "url_kwargs": {"slug": "about-author"},
                "icon": "icon-[tabler--user-circle]",
                "perms": [],  # 公开访问，无权限要求
            },
        ],
    },
]
