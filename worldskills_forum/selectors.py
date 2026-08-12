from django.db.models import Count, DateTimeField, Max, OuterRef, Q, Subquery

from .models import ForumPost, ForumTopicReadState, Importance, PostType


def get_published_post_feed(user, filters):
    last_viewed = ForumTopicReadState.objects.filter(user=user, topic_id=OuterRef("topic_id")).values("last_viewed_at")[:1]
    queryset = (
        ForumPost.objects.filter(translation__isnull=False)
        .select_related("topic", "topic__module", "topic__category", "translation", "created_by", "source_role")
        .prefetch_related("topic__tags", "attachments")
        .annotate(
            image_count=Count("attachments", filter=Q(attachments__kind="image"), distinct=True),
            attachment_count=Count("attachments", distinct=True),
            user_last_viewed_at=Subquery(last_viewed, output_field=DateTimeField()),
        )
        .order_by("-translation__published_at", "-pk")
    )
    q = filters.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(topic__translated_title__icontains=q) | Q(topic__original_title__icontains=q)
            | Q(topic__summary__icontains=q) | Q(author_name__icontains=q) | Q(source_role__name__icontains=q)
            | Q(original_content__icontains=q) | Q(translation__translated_content__icontains=q)
            | Q(topic__module__name__icontains=q) | Q(topic__tags__name__icontains=q) | Q(topic__category__name__icontains=q)
            | Q(attachments__original_filename__icontains=q) | Q(attachments__caption_zh__icontains=q)
        ).distinct()
    mapping = {"year": "topic__competition_year", "module": "topic__module_id", "category": "topic__category_id", "tag": "topic__tags__id", "post_type": "post_type", "importance": "importance"}
    for key, lookup in mapping.items():
        if filters.get(key):
            queryset = queryset.filter(**{lookup: filters[key]})
    view = filters.get("view")
    if view == "important":
        queryset = queryset.filter(importance__in=[Importance.IMPORTANT, Importance.URGENT])
    elif view == "official":
        queryset = queryset.filter(Q(source_role__is_official=True) | Q(post_type__in=[PostType.OFFICIAL_REPLY, PostType.OFFICIAL_NOTICE, PostType.RULE_CHANGE]))
    elif view == "unread":
        queryset = queryset.filter(Q(user_last_viewed_at__isnull=True) | Q(translation__published_at__gt=Subquery(last_viewed)))
    return queryset


def get_topic_timeline(topic):
    return topic.posts.filter(translation__isnull=False).select_related("translation", "created_by", "updated_by", "source_role").prefetch_related("attachments").order_by("posted_at", "pk")


def get_topic_list_queryset():
    return (
        topic_queryset_base()
        .annotate(post_count=Count("posts", filter=Q(posts__translation__isnull=False), distinct=True), latest_translation_at=Max("posts__translation__published_at"))
        .order_by("-competition_year", "-latest_translation_at", "-pk")
    )


def topic_queryset_base():
    from .models import ForumTopic

    return ForumTopic.objects.select_related("module", "category", "created_by").prefetch_related("tags")
