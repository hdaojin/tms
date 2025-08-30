# accounts/menus.py
"""
定义accounts应用的菜单项
"""

MENUS = [
    {
        "section": "用户信息",
        "items": [
            {
                "name": "个人资料",
                "url_name": "accounts:profile",
                "icon": "icon-[tabler--user-circle]",
                "perms": ["is_authenticated"],
            },
            {
                "name": "管理后台",
                "url_name": "admin:index",
                "icon": "icon-[tabler--settings]",
                "perms": ["is_staff"],
            },
            {
                "name": "邀请注册",
                "url_name": "accounts:generate_invitation",
                "icon": "icon-[tabler--key]",
                "perms": ["is_superuser"],
            },
        ],
    },
]
