from __future__ import annotations

from core.constants import GROUP_ASSISTANT, GROUP_COACH, GROUP_COMPETITOR


ROLE_BADGE_CLASSES = {
    GROUP_COACH: "badge badge-soft badge-primary",
    GROUP_COMPETITOR: "badge badge-soft badge-success",
    GROUP_ASSISTANT: "badge badge-soft badge-info",
    "工作人员": "badge badge-soft badge-secondary",
    "超级用户": "badge badge-soft badge-error",
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

    if user.is_staff and not user.is_superuser and "工作人员" not in seen_role_names:
        role_names.append("工作人员")
        seen_role_names.add("工作人员")

    if user.is_superuser and "超级用户" not in seen_role_names:
        role_names.append("超级用户")
        seen_role_names.add("超级用户")

    if not role_names:
        role_names = ["未分配"]

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
        if role_name == "未分配"
        else ROLE_BADGE_CLASSES.get(role_name, DEFAULT_ROLE_BADGE_CLASS)
    )
    return f"{css_class} {size}".strip()
