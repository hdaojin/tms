# articles/menus.py
"""
定义articles应用的菜单项
"""

MENUS = [
    {
        "section": "文章管理",
        "items": [
            {
                "name": "文章列表",
                "url_name": "articles:list",
                "icon": "tabler--article",
                "perms": ["is_authenticated"],
            },
        ],
    },
]

