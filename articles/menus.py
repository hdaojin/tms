from django.urls import reverse


# 文章菜单项

article_menu_items = [
    {
        "name": "文章列表",
        "url": reverse("articles:list"),
    },
]