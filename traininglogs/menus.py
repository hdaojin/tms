# traininglogs/menus.py
"""
定义traininglogs应用的菜单项
"""

MENUS = [
    {
        "section": "训练日志",
        "items": [
            {
                "name": "我的日志",
                "url_name": "traininglogs:list_training_logs",
                "icon": "icon-[tabler--file-text]",
                "perms": ["is_authenticated"],
            },
            {
                "name": "上传日志",
                "url_name": "traininglogs:upload_training_log",
                "icon": "icon-[tabler--file-plus]",
                "perms": ["is_authenticated"],
            },
        ],
    }
]
