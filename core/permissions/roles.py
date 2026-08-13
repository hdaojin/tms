from __future__ import annotations

from typing import Any


ROLE_COACH = "coach"
ROLE_COMPETITOR = "competitor"
ROLE_ASSISTANT = "assistant"


def get_user_role_codenames(user: Any) -> set[str]:
    """Return stable role identifiers from the user's GroupProfile records."""
    if not getattr(user, "pk", None) or not getattr(user, "is_authenticated", True):
        return set()

    role_codenames = user.groups.values_list("profile__codename", flat=True)
    return {codename for codename in role_codenames if codename}


def user_has_role(user: Any, codename: str) -> bool:
    return codename in get_user_role_codenames(user)
