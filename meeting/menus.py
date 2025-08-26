# meeting/menus.py
"""
定义meeting应用的菜单项
"""

MENUS = [
    {
        "section": "会议记录",
        "items": [
            {
                "name": "浏览会议记录",
                "url_name": "meeting:meeting_list",
                "icon": "tabler--article",
                "perms": ["is_authenticated"],
            },
            {
                "name": "上传会议记录",
                "url_name": "meeting:upload_meeting",
                "icon": "tabler--upload",
                "perms": ["is_authenticated", "meeting.add_meeting"],
            },
        ],
    },
]


