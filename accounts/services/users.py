from __future__ import annotations

from django.utils import timezone

ROLE_STAFF = "工作人员"
ROLE_SUPERUSER = "超级用户"
ROLE_UNASSIGNED = "未分配"

ROLE_BADGE_CLASSES = {
    ROLE_STAFF: "badge badge-soft badge-secondary",
    ROLE_SUPERUSER: "badge badge-soft badge-error",
}
DEFAULT_ROLE_BADGE_CLASS = "badge badge-soft badge-accent"
NO_ROLE_BADGE_CLASS = "badge badge-soft"


def get_user_display_name(user) -> str:
    full_name = f"{user.last_name}{user.first_name}".strip()
    return full_name or user.username


def get_user_full_info(user) -> str:
    name = get_user_display_name(user)
    if name != user.username and user.username:
        return f"{name}({user.username})"
    return name


def get_user_role_badges(user, *, size: str = "") -> list[dict[str, str]]:
    role_names = []
    seen_role_names = set()

    for group in user.groups.all():
        if group.name in seen_role_names:
            continue
        role_names.append(group.name)
        seen_role_names.add(group.name)

    if user.is_staff and not user.is_superuser and ROLE_STAFF not in seen_role_names:
        role_names.append(ROLE_STAFF)
        seen_role_names.add(ROLE_STAFF)

    if user.is_superuser and ROLE_SUPERUSER not in seen_role_names:
        role_names.append(ROLE_SUPERUSER)
        seen_role_names.add(ROLE_SUPERUSER)

    if not role_names:
        role_names = [ROLE_UNASSIGNED]

    return [
        {
            "label": role_name,
            "css_class": _get_role_badge_class(role_name, size=size),
        }
        for role_name in role_names
    ]


def _get_role_badge_class(role_name: str, *, size: str = "") -> str:
    css_class = (
        NO_ROLE_BADGE_CLASS
        if role_name == ROLE_UNASSIGNED
        else ROLE_BADGE_CLASSES.get(role_name, DEFAULT_ROLE_BADGE_CLASS)
    )
    return f"{css_class} {size}".strip()


def fill_leave_date_on_deactivation(user, *, previous_is_active: bool) -> None:
    """账号从有效变为无效时，给空离开日期补上当天日期。"""

    if not previous_is_active or user.is_active:
        return

    from accounts.models import UserProfile

    profile, _created = UserProfile.objects.get_or_create(user=user)
    if profile.leave_date:
        return

    profile.leave_date = timezone.localdate()
    profile.save(update_fields=["leave_date"])
