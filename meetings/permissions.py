from __future__ import annotations


ADD_MEETING_PERMISSION = "meetings.add_meeting"
VIEW_MEETING_PERMISSION = "meetings.view_meeting"
CHANGE_MEETING_PERMISSION = "meetings.change_meeting"
DELETE_MEETING_PERMISSION = "meetings.delete_meeting"


def can_view_meeting(user, meeting=None) -> bool:
    return getattr(user, "is_authenticated", False) and user.has_perm(VIEW_MEETING_PERMISSION)


def can_view_meeting_request(request, meeting) -> bool:
    return can_view_meeting(request.user, meeting)


def can_upload_meeting(user) -> bool:
    return getattr(user, "is_authenticated", False) and (
        getattr(user, "is_superuser", False)
        or user.has_perm(ADD_MEETING_PERMISSION)
    )


def can_delete_meeting(user, meeting=None) -> bool:
    return getattr(user, "is_authenticated", False) and (
        getattr(user, "is_superuser", False)
        or user.has_perm(DELETE_MEETING_PERMISSION)
    )


def can_access_meeting_admin_module(user) -> bool:
    return getattr(user, "is_authenticated", False) and (
        getattr(user, "is_superuser", False)
        or user.has_perm(VIEW_MEETING_PERMISSION)
        or user.has_perm(CHANGE_MEETING_PERMISSION)
        or user.has_perm(ADD_MEETING_PERMISSION)
        or user.has_perm(DELETE_MEETING_PERMISSION)
    )


def can_view_meeting_admin(user, meeting=None) -> bool:
    return getattr(user, "is_authenticated", False) and (
        getattr(user, "is_superuser", False)
        or user.has_perm(VIEW_MEETING_PERMISSION)
        or user.has_perm(CHANGE_MEETING_PERMISSION)
    )


def can_change_meeting_admin(user, meeting=None) -> bool:
    return getattr(user, "is_authenticated", False) and (
        getattr(user, "is_superuser", False)
        or user.has_perm(CHANGE_MEETING_PERMISSION)
    )
