"""会议读取统一先限定可见范围，再进行搜索、排序和分页。"""

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q, Value
from django.db.models.functions import Concat

from .models import Meeting
from .permissions import VIEW_MEETING_PERMISSION, can_view_meeting


def meeting_queryset_for(user, queryset=None):
    queryset = Meeting.objects.all() if queryset is None else queryset
    if not can_view_meeting(user):
        return queryset.none()
    if user.is_superuser:
        return queryset.select_related("uploaded_by")
    roles = Meeting.visible_groups.through.objects.filter(meeting_id=OuterRef("pk"), group__user=user)
    people = Meeting.visible_users.through.objects.filter(meeting_id=OuterRef("pk"), user_id=user.pk)
    return (
        queryset.alias(_role_visible=Exists(roles), _person_visible=Exists(people))
        .filter(Q(is_public=True) | Q(uploaded_by_id=user.pk) | Q(_role_visible=True) | Q(_person_visible=True))
        .select_related("uploaded_by")
    )


def recipient_queryset():
    return get_user_model().objects.with_perm(VIEW_MEETING_PERMISSION).filter(is_active=True)


def search_recipients(queryset, query):
    return (
        queryset.annotate(_full_name=Concat("last_name", "first_name"))
        .filter(Q(username__icontains=query) | Q(_full_name__icontains=query))
        .order_by("last_name", "first_name", "username", "pk")
    )


def search_meetings(queryset, query):
    if not query:
        return queryset
    return queryset.alias(_uploader_name=Concat("uploaded_by__last_name", "uploaded_by__first_name", Value(""))).filter(
        Q(title__icontains=query)
        | Q(file__icontains=query)
        | Q(uploaded_by__username__icontains=query)
        | Q(_uploader_name__icontains=query)
    )
