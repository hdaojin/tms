from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .forms import external_attachment_defaults
from .models import ForumPost, ForumPostAttachment, ForumTopicReadState, ForumTranslation


def _create_attachments(post, user, uploaded_attachments, external_attachment_urls):
    created = []
    try:
        for upload in uploaded_attachments:
            attachment = ForumPostAttachment(
                post=post,
                file=upload,
                original_filename=upload.name,
                file_size=upload.size,
                created_by=user,
            )
            attachment.full_clean()
            created.append(attachment)
            attachment.save()
        for url in external_attachment_urls:
            attachment = ForumPostAttachment(post=post, source_url=url, created_by=user, **external_attachment_defaults(url))
            attachment.full_clean()
            attachment.save()
            created.append(attachment)
    except Exception:
        for attachment in created:
            if attachment.file and attachment.file.name:
                attachment.file.storage.delete(attachment.file.name)
        raise
    return created


def create_published_post(*, topic, post_data, translation_data, user, uploaded_attachments=(), external_attachment_urls=()):
    written_files = []
    try:
        with transaction.atomic():
            post = ForumPost(topic=topic, created_by=user, updated_by=user, **post_data)
            post.full_clean()
            post.save()
            translation = ForumTranslation(post=post, translated_by=user, updated_by=user, published_at=timezone.now(), **translation_data)
            translation.full_clean()
            translation.save()
            attachments = _create_attachments(post, user, uploaded_attachments, external_attachment_urls)
            written_files = [item for item in attachments if item.file]
            return post
    except Exception:
        for attachment in written_files:
            if attachment.file and attachment.file.name:
                attachment.file.storage.delete(attachment.file.name)
        raise


def update_published_post(*, post, post_data, translation_data, user):
    with transaction.atomic():
        for key, value in post_data.items():
            setattr(post, key, value)
        post.updated_by = user
        post.full_clean()
        post.save()
        translation = post.translation
        translation.translated_content = translation_data["translated_content"]
        translation.updated_by = user
        translation.full_clean()
        translation.save()
    return post


def add_post_attachments(*, post, user, uploaded_attachments=(), external_attachment_urls=()):
    with transaction.atomic():
        return _create_attachments(post, user, uploaded_attachments, external_attachment_urls)


def mark_topic_viewed(user, topic, viewed_at=None):
    return ForumTopicReadState.objects.update_or_create(
        user=user,
        topic=topic,
        defaults={"last_viewed_at": viewed_at or timezone.now()},
    )[0]
