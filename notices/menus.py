from django.urls import reverse


menu_items = (
    {"name": "通知列表", "url": reverse("notices:notice_list")},
    {"name": "发布通知", "url": reverse("notices:notice_create")},
)