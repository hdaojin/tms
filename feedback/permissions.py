from __future__ import annotations

from accounts.services.users import get_user_display_name


MANAGE_FEEDBACK_PERMISSION = "feedback.manage_feedback"
VIEW_PRIVATE_FEEDBACK_PERMISSION = "feedback.view_private_feedback"
VIEW_ANONYMOUS_IDENTITY_PERMISSION = "feedback.view_anonymous_identity"


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def can_manage_feedback(user) -> bool:
    return bool(_is_authenticated(user) and (user.is_superuser or user.has_perm(MANAGE_FEEDBACK_PERMISSION)))


def can_view_private_feedback(user) -> bool:
    return bool(
        _is_authenticated(user)
        and (user.is_superuser or user.has_perm(VIEW_PRIVATE_FEEDBACK_PERMISSION))
    )


def can_view_anonymous_identity(user) -> bool:
    return bool(
        _is_authenticated(user)
        and (user.is_superuser or user.has_perm(VIEW_ANONYMOUS_IDENTITY_PERMISSION))
    )


def can_view_feedback(user, feedback) -> bool:
    if not _is_authenticated(user):
        return False
    if not feedback.is_private:
        return True
    return bool(
        can_view_private_feedback(user)
        or feedback.author_id == getattr(user, "pk", None)
    )


def can_reply_feedback(user, feedback) -> bool:
    if not can_view_feedback(user, feedback):
        return False
    if feedback.status == "closed" and not can_manage_feedback(user):
        return False
    return True


def get_feedback_author_label(user, feedback) -> str:
    if feedback.is_anonymous:
        if (
            feedback.author_id
            and can_view_feedback(user, feedback)
            and can_view_anonymous_identity(user)
            and feedback.author
        ):
            return f"匿名用户（真实：{get_user_display_name(feedback.author)}）"
        return "匿名用户"
    if not feedback.author:
        return "已删除用户"
    return get_user_display_name(feedback.author)


def get_reply_author_label(user, feedback, reply) -> str:
    is_anonymous_author_reply = bool(
        feedback.is_anonymous
        and feedback.author_id
        and reply.author_id
        and reply.author_id == feedback.author_id
    )
    if is_anonymous_author_reply:
        if can_view_feedback(user, feedback) and can_view_anonymous_identity(user) and reply.author:
            return f"匿名反馈人（真实：{get_user_display_name(reply.author)}）"
        return "匿名反馈人"
    if not reply.author:
        return "已删除用户"
    return get_user_display_name(reply.author)


def can_view_attachment(user, attachment) -> bool:
    return can_view_feedback(user, attachment.feedback)
