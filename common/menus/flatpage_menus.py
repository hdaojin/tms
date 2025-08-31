# pages/menus.py
"""
页面菜单项注册
"""

MENUS = [
    {
        "section": None,  # flatpage菜单不显示section标题
        "items": [
            {
                "name": "关于本站",
                "url": "/about/",
                "icon": "icon-[tabler--info-circle]",
                "perms": [],  # 公开访问，无权限要求
            },
            {
                "name": "关于作者",
                "url": "/about-author/",
                "icon": "icon-[tabler--user-circle]",
                "perms": [],  # 公开访问，无权限要求
            },
        ],
    },
]
