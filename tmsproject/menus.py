from django.urls import reverse

# 主菜单项
main_menu_items = [
        {
            "name": "首页",
            "url": "/",
        },
        {
            "name": "讲义",
            "url": "#",
        },
        {
            "name": "日志",
            "url": reverse("traininglogs:list_training_logs"),
        },
        {
            "name": "文章",
            "url": reverse("articles:list"),
        },
        {
            "name": "关于",
            "url": reverse("pages:page_detail", kwargs={"slug": "about"}),
        },
    ]

