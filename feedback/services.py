from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.constants import FEEDBACK_ATTACHMENT_MAX_COUNT, FEEDBACK_ATTACHMENT_MAX_TOTAL_SIZE_MB
from core.uploads import FEEDBACK_ATTACHMENT_UPLOAD_SPEC

from .models import Feedback, FeedbackAttachment, FeedbackReply, FeedbackStatus, sanitize_original_filename
from .permissions import can_manage_feedback, can_reply_feedback


def validate_feedback_attachments(attachments: Iterable) -> list:
    files = [attachment for attachment in attachments or () if attachment]
    if len(files) > FEEDBACK_ATTACHMENT_MAX_COUNT:
        raise ValidationError(f"每次最多添加 {FEEDBACK_ATTACHMENT_MAX_COUNT} 个附件。")

    total_size = sum(getattr(attachment, "size", 0) or 0 for attachment in files)
    max_total_size = FEEDBACK_ATTACHMENT_MAX_TOTAL_SIZE_MB * 1024 * 1024
    if total_size > max_total_size:
        raise ValidationError(f"每次附件总大小不能超过 {FEEDBACK_ATTACHMENT_MAX_TOTAL_SIZE_MB}MB。")

    for attachment in files:
        FEEDBACK_ATTACHMENT_UPLOAD_SPEC.validate_file(attachment)
    return files


def _delete_written_files(attachments: Iterable[FeedbackAttachment]) -> None:
    for attachment in attachments:
        if attachment.file and attachment.file.name:
            try:
                attachment.file.storage.delete(attachment.file.name)
            except (OSError, ValueError):
                pass


def _create_attachments(*, feedback, reply=None, actor, attachments) -> list[FeedbackAttachment]:
    created: list[FeedbackAttachment] = []
    for upload in attachments:
        attachment = FeedbackAttachment(
            feedback=feedback,
            reply=reply,
            file=upload,
            original_filename=sanitize_original_filename(upload.name),
            file_size=upload.size,
            content_type=getattr(upload, "content_type", "") or "",
            uploaded_by=actor,
        )
        attachment.full_clean()
        try:
            attachment.save()
        except Exception:
            _delete_written_files([attachment])
            raise
        created.append(attachment)
    return created


def create_feedback(*, data: Mapping, attachments=(), actor) -> Feedback:
    files = validate_feedback_attachments(attachments)
    written_files: list[FeedbackAttachment] = []
    try:
        with transaction.atomic():
            feedback = Feedback(
                category=data["category"],
                title=str(data["title"]).strip(),
                content=str(data["content"]).strip(),
                author=actor,
                is_anonymous=bool(data.get("is_anonymous", False)),
                is_private=bool(data.get("is_private", False)),
            )
            feedback.full_clean()
            feedback.save()
            written_files = _create_attachments(
                feedback=feedback,
                actor=actor,
                attachments=files,
            )
            return feedback
    except Exception:
        _delete_written_files(written_files)
        raise


def add_feedback_reply(*, feedback, content: str, attachments=(), actor) -> FeedbackReply:
    written_files: list[FeedbackAttachment] = []
    try:
        with transaction.atomic():
            locked_feedback = Feedback.objects.select_for_update().get(pk=feedback.pk)
            if not can_reply_feedback(actor, locked_feedback):
                raise PermissionDenied("当前用户不能回复该反馈。")
            files = validate_feedback_attachments(attachments)
            reply = FeedbackReply(feedback=locked_feedback, author=actor, content=content.strip())
            reply.full_clean()
            reply.save()
            written_files = _create_attachments(
                feedback=locked_feedback,
                reply=reply,
                actor=actor,
                attachments=files,
            )
            now = timezone.now()
            Feedback.objects.filter(pk=locked_feedback.pk).update(updated_at=now)
            feedback.updated_at = now
            return reply
    except Exception:
        _delete_written_files(written_files)
        raise


def update_feedback_status(*, feedback, status: str, resolution: str, actor) -> Feedback:
    if not can_manage_feedback(actor):
        raise PermissionDenied("当前用户不能管理意见反馈。")
    if status not in {value for value, _label in FeedbackStatus.choices}:
        raise ValidationError({"status": "反馈状态无效。"})

    with transaction.atomic():
        locked_feedback = Feedback.objects.select_for_update().get(pk=feedback.pk)
        locked_feedback.status = status
        locked_feedback.resolution = resolution.strip()
        if status in {FeedbackStatus.RESOLVED, FeedbackStatus.CLOSED}:
            locked_feedback.resolved_by = actor
            locked_feedback.resolved_at = timezone.now()
        else:
            locked_feedback.resolved_by = None
            locked_feedback.resolved_at = None
        locked_feedback.full_clean()
        locked_feedback.save(
            update_fields=[
                "status",
                "resolution",
                "resolved_by",
                "resolved_at",
                "updated_at",
            ]
        )
        feedback.status = locked_feedback.status
        feedback.resolution = locked_feedback.resolution
        feedback.resolved_by = locked_feedback.resolved_by
        feedback.resolved_at = locked_feedback.resolved_at
        feedback.updated_at = locked_feedback.updated_at
    return feedback
