from django import template

from accounts.services.users import get_user_display_name
from feedback.permissions import get_feedback_author_label, get_reply_author_label


register = template.Library()


@register.simple_tag(takes_context=True)
def feedback_author(context, feedback):
    return get_feedback_author_label(context["request"].user, feedback)


@register.simple_tag(takes_context=True)
def reply_author(context, feedback, reply):
    return get_reply_author_label(context["request"].user, feedback, reply)


@register.simple_tag
def user_display(user):
    return get_user_display_name(user) if user else "已删除用户"
