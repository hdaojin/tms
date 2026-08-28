from django.conf import settings
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site

from .models import SiteConfig


SITE_CONFIG_DEFAULTS = {
    "site_name": "Training management system",
    "site_short_name": "TMS",
    "site_description": "A training management system for skill competitions.",
    "site_keywords": "training, management, skills, competitions",
    "site_author": "hdaojin",
    "site_copyright": "TMS 版权所有",
}

FLAT_PAGE_DEFAULTS = (
    {
        "url": "/about/site/",
        "title": "关于 TMS",
        "content": (
            "Training Management System (TMS) 是一个用于技能竞赛培训管理的系统，"
            "旨在帮助教练和选手更高效地管理和记录训练日常。"
        ),
    },
    {
        "url": "/about/author/",
        "title": "关于作者",
        "content": "本系统由 hdaojin 开发和维护。如有任何问题或建议，欢迎联系作者。",
    },
)


def bootstrap_defaults():
    created_count = 0
    existing_count = 0

    _config, created = SiteConfig.objects.get_or_create(pk=1, defaults=SITE_CONFIG_DEFAULTS)
    created_count += int(created)
    existing_count += int(not created)

    site = None
    for page_defaults in FLAT_PAGE_DEFAULTS:
        page, created = FlatPage.objects.get_or_create(
            url=page_defaults["url"],
            defaults={
                "title": page_defaults["title"],
                "content": page_defaults["content"],
                "enable_comments": False,
                "registration_required": False,
            },
        )
        if created:
            if site is None:
                site = Site.objects.get(pk=settings.SITE_ID)
            page.sites.add(site)
            created_count += 1
        else:
            existing_count += 1

    return {"created": created_count, "existing": existing_count}
