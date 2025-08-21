from django.urls import reverse

# 基础训练日志菜单项（保持静态部分）
BASE_ITEMS = (
    ("我的日志", "traininglogs:list_training_logs"),
    ("日志统计", "traininglogs:training_log_statistics"),
    ("上传日志", "traininglogs:upload_training_log"),
)

# 角色 -> 对向角色菜单标题
COUNTERPART_LABEL = {
    '教练': '选手日志',
    '选手': '教练日志',
}

def get_training_log_menu_items(user):
    """返回当前用户的训练日志菜单项列表，包含基础项及其对向角色日志入口。"""
    # 构造基础菜单
    menu_items = [
        {"name": name, "url": reverse(url_name)} for name, url_name in BASE_ITEMS
    ]

    if not user.is_authenticated:
        return menu_items

    # 获取用户所属首个匹配角色（若两个都在，以教练优先）
    groups = set(user.groups.values_list('name', flat=True))
    role = '教练' if '教练' in groups else ('选手' if '选手' in groups else None)
    if role and role in COUNTERPART_LABEL:
        counterpart_item = {
            "name": COUNTERPART_LABEL[role],
            "url": reverse("traininglogs:counterpart_training_logs"),
        }
        # 插入到“我的日志”后面（索引1位置）
        menu_items.insert(1, counterpart_item)
    return menu_items
