from django.urls import reverse

# 用户菜单项
base_user_menu_items = [
    {
        "name": "个人信息",
        "url": reverse("accounts:profile"),
    },
    {
        "name": "修改密码",
        "url": "#",
    },
   
]

admin_menu_items = [
    {
        "name": "后台管理",
        "url": reverse("admin:index"),
    },
    {
        "name": "邀请注册",
        "url": reverse("accounts:generate_invitation"),
    }
]


def get_user_menu_items(user):
    menu_items = base_user_menu_items.copy()
    if user.is_authenticated and user.is_superuser:
        menu_items.extend(admin_menu_items)
    return menu_items
