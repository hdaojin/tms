from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.uploads import FEEDBACK_ATTACHMENT_UPLOAD_SPEC, PrivateMediaStorage
from core.utils.signals import register_file_cleanup_signals


SAFE_IMAGE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp"})


def feedback_attachment_upload_path(instance: "FeedbackAttachment", filename: str) -> str:
    extension = Path(filename).suffix.lower()
    date_path = timezone.localdate().strftime("%Y/%m/%d")
    return f"{date_path}/{uuid.uuid4().hex}{extension}"


def sanitize_original_filename(filename: str | None) -> str:
    """将上传文件名转换为可安全展示和下载的名称。"""
    value = str(filename or "").replace("/", "_").replace("\\", "_").strip()
    value = "".join(char for char in value if char.isprintable())
    value = value[:255]
    return value if value not in {"", ".", ".."} else "附件"


class FeedbackCategory(models.Model):
    code = models.CharField("分类代码", max_length=20, unique=True)
    name = models.CharField("分类名称", max_length=120)
    description = models.TextField("说明", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    default_private = models.BooleanField("默认设为私密", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["order", "code"]
        verbose_name = "反馈分类"
        verbose_name_plural = "反馈分类"

    def __str__(self) -> str:
        return self.name


class FeedbackStatus(models.TextChoices):
    OPEN = "open", "待处理"
    IN_PROGRESS = "in_progress", "处理中"
    RESOLVED = "resolved", "已解决"
    CLOSED = "closed", "已关闭"


class Feedback(models.Model):
    category = models.ForeignKey(
        FeedbackCategory,
        models.PROTECT,
        related_name="feedbacks",
        verbose_name="反馈类型",
    )
    title = models.CharField("标题", max_length=200)
    content = models.TextField("详细描述")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        null=True,
        related_name="feedbacks_created",
        verbose_name="提交人",
    )
    is_anonymous = models.BooleanField("匿名提交", default=False)
    is_private = models.BooleanField("仅工作人员可见", default=False, db_index=True)
    status = models.CharField(
        "状态",
        max_length=20,
        choices=FeedbackStatus,
        default=FeedbackStatus.OPEN,
        db_index=True,
    )
    resolution = models.TextField("处理结果", blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks_resolved",
        verbose_name="处理人",
    )
    resolved_at = models.DateTimeField("处理时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True, db_index=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        verbose_name = "意见反馈"
        verbose_name_plural = "意见反馈"
        permissions = [
            ("manage_feedback", "管理意见反馈"),
            ("view_private_feedback", "查看私密反馈"),
            ("view_anonymous_identity", "查看匿名反馈人身份"),
        ]
        indexes = [
            models.Index(fields=["category", "status"], name="feedback_fe_categor_ca3927_idx"),
            models.Index(fields=["is_private", "status"]),
        ]

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        if not self.title or not self.title.strip():
            errors["title"] = "标题不能为空。"
        if not self.content or not self.content.strip():
            errors["content"] = "详细描述不能为空。"
        if self.status in {FeedbackStatus.RESOLVED, FeedbackStatus.CLOSED} and not self.resolution.strip():
            errors["resolution"] = "已解决或已关闭的反馈必须填写处理结果。"
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"#{self.pk or '新'} {self.title}"


class FeedbackReply(models.Model):
    feedback = models.ForeignKey(Feedback, models.CASCADE, related_name="replies", verbose_name="反馈")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        null=True,
        related_name="feedback_replies",
        verbose_name="回复人",
    )
    content = models.TextField("回复内容")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = "反馈回复"
        verbose_name_plural = "反馈回复"

    def clean(self) -> None:
        super().clean()
        if not self.content or not self.content.strip():
            raise ValidationError({"content": "回复内容不能为空。"})

    def __str__(self) -> str:
        return f"#{self.feedback_id} 的回复"


class FeedbackAttachment(models.Model):
    feedback = models.ForeignKey(Feedback, models.CASCADE, related_name="attachments", verbose_name="反馈")
    reply = models.ForeignKey(
        FeedbackReply,
        models.CASCADE,
        related_name="attachments",
        null=True,
        blank=True,
        verbose_name="回复",
    )
    file = models.FileField(
        "附件文件",
        storage=PrivateMediaStorage("feedback"),
        upload_to=feedback_attachment_upload_path,
        validators=FEEDBACK_ATTACHMENT_UPLOAD_SPEC.validators(),
    )
    original_filename = models.CharField("原始文件名", max_length=255)
    file_size = models.PositiveBigIntegerField("文件大小")
    content_type = models.CharField("MIME 类型", max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        null=True,
        related_name="feedback_attachments_uploaded",
        verbose_name="上传人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = "反馈附件"
        verbose_name_plural = "反馈附件"

    def clean(self) -> None:
        super().clean()
        if self.reply_id and self.feedback_id:
            if self.reply.feedback_id != self.feedback_id:
                raise ValidationError({"reply": "回复附件必须属于同一条反馈。"})
        self.original_filename = sanitize_original_filename(
            self.original_filename or (Path(self.file.name).name if self.file else "")
        )

    def save(self, *args, **kwargs):
        if self.file:
            self.original_filename = sanitize_original_filename(
                self.original_filename or Path(self.file.name).name
            )
            self.file_size = getattr(self.file, "size", self.file_size)
            self.content_type = self.content_type or mimetypes.guess_type(self.file.name)[0] or "application/octet-stream"
        super().save(*args, **kwargs)

    @property
    def is_safe_image(self) -> bool:
        filename = (self.file.name if self.file else "") or self.original_filename
        return Path(filename).suffix.lower().lstrip(".") in SAFE_IMAGE_EXTENSIONS

    def __str__(self) -> str:
        return self.original_filename


register_file_cleanup_signals(FeedbackAttachment, file_field="file")
