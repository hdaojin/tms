SITE_CONFIG_DEFAULTS = {
    "pk": 1,
    "site_name": "Training management system",
    "site_short_name": "TMS",
    "site_description": "A training management system for skill competitions.",
    "site_keywords": "training, management, skills, competitions",
    "site_author": "hdaojin",
    "site_copyright": "TMS 版权所有",
}

FLAT_PAGES = [
    {
        "url": "/about/site/",
        "title": "关于 TMS",
        "content": "Training Management System (TMS) 是一个用于技能竞赛培训管理的系统，旨在帮助教练和选手更高效地管理和记录训练日常。",
        "enable_comments": False,
        "registration_required": False,
    },
    {
        "url": "/about/author/",
        "title": "关于作者",
        "content": "本系统由 hdaojin 开发和维护。如有任何问题或建议，欢迎联系作者。",
        "enable_comments": False,
        "registration_required": False,
    },
]

BOOTSTRAP_DATA = [
    {"label": "站点配置", "model": "core.SiteConfig", "key_fields": ("pk",), "records": [SITE_CONFIG_DEFAULTS]},
    {"label": "默认说明页面", "model": "flatpages.FlatPage", "key_fields": ("url",), "records": FLAT_PAGES, "flatpage_current_site": True},
]
