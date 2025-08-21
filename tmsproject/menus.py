from django.urls import reverse

# 主菜单项
main_menu_items = (
    ("首页", "/"),
    ("日志", reverse("traininglogs:list_training_logs")),
    ("会议", reverse("meeting:meeting_list")),
    ("通知", reverse("notices:notice_list")),
    ("关于", reverse("pages:page_detail", kwargs={"slug": "about"})),
)


def get_main_menu_items(user):
    """返回主菜单项列表"""
    if user.is_authenticated:
        return [
            {"name": name, "url": url} for name, url in main_menu_items
        ]


