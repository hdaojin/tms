from django.urls import reverse


def get_meeting_menu_items(user):
    """返回当前用户的会议管理菜单项列表"""
    menu_items = [
        {"name": "会议记录", "url": reverse("meeting:meeting_list")},
    ]
    
    # 只有班务人员才能看到上传选项
    if user.is_authenticated and user.groups.filter(name='班务').exists():
        menu_items.append({
            "name": "上传会议记录",
            "url": reverse("meeting:upload_meeting"),
        })
    
    return menu_items
