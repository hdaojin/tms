from core.models import SiteConfig


def apply_default_registration_group(user) -> None:
    default_group = SiteConfig.get_solo().default_registration_group
    if default_group is not None:
        user.groups.add(default_group)
