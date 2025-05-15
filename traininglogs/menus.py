from django.urls import reverse

# 基础训练日志菜单项
base_training_log_menu_items = [
    {
        "name": "我的日志",
        "url": reverse("traininglogs:list_training_logs"),
    },
    {
        "name": "上传日志",
        "url": reverse("traininglogs:upload_training_log"),
    },
    {
        "name": "日志统计",
        "url": reverse("traininglogs:training_log_statistics"),
    }
]

# 教练特有的训练日志菜单项
coach_training_log_menu_items = [
    {
        "name": "选手日志",
        # "url": reverse("traininglogs:athlete_logs"),
        "url": "#",
    }
]

competitor_training_log_menu_items = [
    {
       "name": "教练日志",
       "url": "#", 
    }
]


def get_training_log_menu_items(user):
    """
    根据用户的分组动态获取训练日志菜单项
    
    Args:
        user: 当前登录用户
        
    Returns:
        list: 训练日志菜单项列表
    """
    menu_items = base_training_log_menu_items.copy()
    
    # 检查用户是否登录以及是否属于教练组
    if user.is_authenticated:
        user_groups = user.groups.values_list('name', flat=True)
        if '教练' in user_groups:
            # 如果用户是教练，添加教练特有的菜单项
            menu_items.extend(coach_training_log_menu_items)
        elif '选手' in user_groups:
            # 如果用户是选手，添加选手特有的菜单项
            menu_items.extend(competitor_training_log_menu_items)
    
    return menu_items
