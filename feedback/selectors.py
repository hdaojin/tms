from __future__ import annotations

from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404

from .models import Feedback, FeedbackAttachment, FeedbackCategory, FeedbackReply, FeedbackStatus
from .permissions import can_view_private_feedback


def visible_feedbacks_for(user):
    """返回当前用户可见的反馈范围，所有列表筛选都必须从这里开始。"""
    if not getattr(user, "is_authenticated", False):
        return Feedback.objects.none()

    queryset = (
        Feedback.objects.select_related("author", "resolved_by")
        .annotate(
            reply_count=Count("replies", distinct=True),
            attachment_count=Count("attachments", distinct=True),
        )
        .order_by("-updated_at", "-pk")
    )
    if not can_view_private_feedback(user):
        queryset = queryset.filter(Q(is_private=False) | Q(author_id=user.pk))
    return queryset


def filtered_feedbacks_for(user, *, category="", status="", query="", scope=""):
    queryset = visible_feedbacks_for(user)
    if category in {value for value, _label in FeedbackCategory.choices}:
        queryset = queryset.filter(category=category)
    if status in {value for value, _label in FeedbackStatus.choices}:
        queryset = queryset.filter(status=status)
    if scope == "my":
        queryset = queryset.filter(author_id=user.pk)
    query = (query or "").strip()
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(content__icontains=query))
    return queryset


def feedback_detail_for(user, pk):
    reply_attachments = FeedbackAttachment.objects.select_related("uploaded_by")
    replies = (
        FeedbackReply.objects.select_related("author")
        .prefetch_related(Prefetch("attachments", queryset=reply_attachments))
        .order_by("created_at", "pk")
    )
    queryset = visible_feedbacks_for(user).prefetch_related(
        Prefetch(
            "attachments",
            queryset=FeedbackAttachment.objects.filter(reply__isnull=True).select_related("uploaded_by"),
        ),
        Prefetch("replies", queryset=replies),
    )
    return get_object_or_404(queryset, pk=pk)
