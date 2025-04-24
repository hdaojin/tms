from django.urls import reverse

# 页面菜单项

page_menu_items = [
    {
        "name": "关于本站",
        "url": reverse("pages:page_detail", kwargs={"slug": "about"}),
    },
    {
        "name": "关于作者",
        "url": reverse("pages:page_detail", kwargs={"slug": "about-author"}),
    },
    {
        "name": "联系我",
        "url": reverse("pages:page_detail", kwargs={"slug": "contact-me"}),
    },
    {
        "name": "使用协议",
        "url": reverse("pages:page_detail", kwargs={"slug": "terms-of-service"}),
    },
    {
        "name": "隐私政策",
        "url": reverse("pages:page_detail", kwargs={"slug": "privacy-policy"}),
    },
    {
        "name": "免责声明",
        "url": reverse("pages:page_detail", kwargs={"slug": "disclaimer"}),
    },
]