from __future__ import annotations


def get_user_display_name(user) -> str:
    full_name = f"{user.last_name}{user.first_name}".strip()
    return full_name or user.username


def get_user_full_info(user) -> str:
    name = get_user_display_name(user)
    if name != user.username and user.username:
        return f"{name}({user.username})"
    return name