from common.menu_utils import build_menu_items, create_menu_item


# 页面菜单配置
PAGES_MENU_CONFIG = [
    create_menu_item(
        name="关于本站",
        url_name="pages:page_detail",
        url_kwargs={"slug": "about"},
        icon="icon-[tabler--info-circle]",
        order=1,
    ),
    create_menu_item(
        name="关于作者",
        url_name="pages:page_detail",
        url_kwargs={"slug": "about-author"},
        icon="icon-[tabler--user-circle]",
        order=2,
    ),
    # create_menu_item(
    #     name="联系我",
    #     url_name="pages:page_detail",
    #     url_kwargs={"slug": "contact-me"},
    #     icon="icon-[tabler--mail]",
    #     order=3,
    # ),
    # create_menu_item(
    #     name="使用协议",
    #     url_name="pages:page_detail", 
    #     url_kwargs={"slug": "terms-of-service"},
    #     icon="icon-[tabler--file-text]",
    #     order=4,
    # ),
    # create_menu_item(
    #     name="隐私政策",
    #     url_name="pages:page_detail",
    #     url_kwargs={"slug": "privacy-policy"},
    #     icon="icon-[tabler--shield-lock]",
    #     order=5,
    # ),
    # create_menu_item(
    #     name="免责声明",
    #     url_name="pages:page_detail",
    #     url_kwargs={"slug": "disclaimer"},
    #     icon="icon-[tabler--alert-triangle]",
    #     order=6,
    # ),
]


def get_pages_menu_items(user):
    """返回页面菜单项列表"""
    # 页面菜单对所有用户可见，包括未认证用户
    return build_menu_items(user, PAGES_MENU_CONFIG)
