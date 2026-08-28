from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.uploads import PrivateMediaStorage, WORLDSKILLS_FORUM_ATTACHMENT_UPLOAD_SPEC
from core.utils.signals import register_file_cleanup_signals


base_http_url_validator = URLValidator(schemes=["http", "https"])


def http_url_validator(value):
    base_http_url_validator(value)
    parsed = urlsplit(value)
    if parsed.username or parsed.password:
        raise ValidationError("来源链接不能包含用户名或密码。")


SAFE_IMAGE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "gif", "webp"})


class Importance(models.TextChoices):
    NORMAL = "normal", "普通"
    IMPORTANT = "important", "重要"
    URGENT = "urgent", "紧急"


class TopicStatus(models.TextChoices):
    ACTIVE = "active", "持续讨论"
    CONFIRMED = "confirmed", "已确认"
    CLOSED = "closed", "已结束"
    ARCHIVED = "archived", "已归档"


class AttachmentKind(models.TextChoices):
    IMAGE = "image", "图片"
    FILE = "file", "附件"


def forum_attachment_upload_path(instance, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    date_path = timezone.localdate().strftime("%Y/%m/%d")
    return f"{date_path}/{uuid.uuid4().hex}{ext}"


class SluggedNameModel(models.Model):
    name = models.CharField("名称", max_length=100, unique=True)
    slug = models.SlugField("标识", max_length=120, unique=True, allow_unicode=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        if not self.slug:
            raise ValidationError({"slug": "名称无法自动生成有效标识，请手工填写标识。"})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ForumCategory(SluggedNameModel):
    sort_order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["sort_order", "name", "pk"]
        verbose_name = "论坛分类"
        verbose_name_plural = "论坛分类"


class ForumModule(SluggedNameModel):
    sort_order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        ordering = ["sort_order", "name", "pk"]
        verbose_name = "论坛模块"
        verbose_name_plural = "论坛模块"


class ForumSourceRole(SluggedNameModel):
    sort_order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    is_official = models.BooleanField("官方来源", default=False)
    allows_detail = models.BooleanField("允许填写身份补充说明", default=False)

    class Meta:
        ordering = ["sort_order", "name", "pk"]
        verbose_name = "论坛来源身份"
        verbose_name_plural = "论坛来源身份"


class ForumPostType(models.Model):
    code = models.CharField("类型代码", max_length=30, unique=True)
    name = models.CharField("类型名称", max_length=120)
    description = models.TextField("说明", blank=True)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    is_official = models.BooleanField("官方信息", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["order", "code"]
        verbose_name = "论坛信息类型"
        verbose_name_plural = "论坛信息类型"

    def __str__(self):
        return self.name


class ForumTag(SluggedNameModel):
    class Meta:
        ordering = ["name", "pk"]
        verbose_name = "论坛标签"
        verbose_name_plural = "论坛标签"


class ForumTopic(models.Model):
    competition_year = models.PositiveSmallIntegerField("世赛年份", db_index=True)
    translated_title = models.CharField("主题中文标题", max_length=300)
    original_title = models.CharField("论坛原始标题", max_length=500)
    source_url = models.URLField("论坛主题链接", max_length=1000, validators=[http_url_validator])
    source_topic_id = models.CharField("论坛主题 ID", max_length=120, blank=True)
    summary = models.TextField("中文摘要", blank=True)
    module = models.ForeignKey(ForumModule, models.PROTECT, related_name="topics", verbose_name="模块")
    category = models.ForeignKey(ForumCategory, models.PROTECT, related_name="topics", verbose_name="分类")
    tags = models.ManyToManyField(ForumTag, blank=True, related_name="topics", verbose_name="标签")
    status = models.CharField("状态", max_length=20, choices=TopicStatus, default=TopicStatus.ACTIVE, db_index=True)
    importance = models.CharField("重要程度", max_length=20, choices=Importance, default=Importance.NORMAL, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, related_name="forum_topics_created", verbose_name="创建人")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, related_name="forum_topics_updated", verbose_name="更新人")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-competition_year", "-updated_at", "-pk"]
        verbose_name = "论坛主题"
        verbose_name_plural = "论坛主题"
        permissions = [("change_all_forum_content", "管理全部论坛内容")]
        indexes = [models.Index(fields=["category"])]

    def clean(self):
        super().clean()
        if self.source_topic_id and ForumTopic.objects.exclude(pk=self.pk).filter(source_topic_id=self.source_topic_id).exists():
            raise ValidationError({"source_topic_id": "该论坛主题 ID 已存在。"})
        if self.source_url and ForumTopic.objects.exclude(pk=self.pk).filter(source_url=self.source_url).exists():
            raise ValidationError({"source_url": "该论坛主题链接已存在。"})

    def __str__(self):
        return self.translated_title


class ForumPost(models.Model):
    topic = models.ForeignKey(ForumTopic, models.CASCADE, related_name="posts", verbose_name="主题")
    author_name = models.CharField("原作者", max_length=200)
    source_role = models.ForeignKey(
        ForumSourceRole,
        models.PROTECT,
        related_name="posts",
        verbose_name="来源身份",
    )
    source_role_detail = models.CharField("身份补充说明", max_length=200, blank=True)
    posted_at = models.DateTimeField("论坛原始发布时间", default=timezone.now)
    source_url = models.URLField("原帖链接", max_length=1000, blank=True, validators=[http_url_validator])
    source_post_id = models.CharField("论坛帖子 ID", max_length=120, blank=True, db_index=True)
    post_type = models.ForeignKey(
        ForumPostType,
        models.PROTECT,
        related_name="posts",
        verbose_name="信息类型",
    )
    importance = models.CharField("重要程度", max_length=20, choices=Importance, default=Importance.NORMAL, db_index=True)
    original_content = models.TextField("英文原文")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, related_name="forum_posts_created", verbose_name="创建人")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, related_name="forum_posts_updated", verbose_name="更新人")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["posted_at", "pk"]
        verbose_name = "论坛帖子"
        verbose_name_plural = "论坛帖子"
        indexes = [models.Index(fields=["topic", "posted_at"])]

    def clean(self):
        super().clean()
        if self.source_role_id and not self.source_role.allows_detail:
            self.source_role_detail = ""
        if self.source_post_id and self.topic_id and ForumPost.objects.exclude(pk=self.pk).filter(topic_id=self.topic_id, source_post_id=self.source_post_id).exists():
            raise ValidationError({"source_post_id": "该主题内已存在相同的论坛帖子 ID。"})

    def __str__(self):
        return f"{self.topic} - {self.author_name}"


class ForumTranslation(models.Model):
    post = models.OneToOneField(ForumPost, models.CASCADE, related_name="translation", verbose_name="帖子")
    translated_content = models.TextField("中文翻译")
    translated_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, related_name="forum_translations_published", verbose_name="翻译人")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, related_name="forum_translations_updated", verbose_name="更新人")
    published_at = models.DateTimeField("TMS 发布时间", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-published_at", "-pk"]
        verbose_name = "论坛翻译"
        verbose_name_plural = "论坛翻译"

    def __str__(self):
        return f"{self.post} 的中文翻译"


class ForumPostAttachment(models.Model):
    post = models.ForeignKey(ForumPost, models.CASCADE, related_name="attachments", verbose_name="帖子")
    kind = models.CharField("类型", max_length=10, choices=AttachmentKind, default=AttachmentKind.FILE)
    file = models.FileField(
        "本地归档文件",
        storage=PrivateMediaStorage("worldskills_forum"),
        upload_to=forum_attachment_upload_path,
        blank=True,
        validators=WORLDSKILLS_FORUM_ATTACHMENT_UPLOAD_SPEC.validators(),
    )
    original_filename = models.CharField("原始文件名", max_length=255)
    source_url = models.URLField("论坛原附件链接", max_length=1000, blank=True, validators=[http_url_validator])
    caption_zh = models.CharField("中文说明", max_length=500, blank=True)
    sort_order = models.PositiveIntegerField("排序", default=0)
    file_size = models.PositiveBigIntegerField("文件大小", null=True, blank=True)
    content_type = models.CharField("MIME 类型", max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, related_name="forum_attachments_created", verbose_name="创建人")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "论坛附件"
        verbose_name_plural = "论坛附件"

    def clean(self):
        super().clean()
        if not self.file and not self.source_url:
            raise ValidationError("本地归档文件和论坛原附件链接至少填写一项。")
        self.original_filename = self.original_filename.replace("/", "_").replace("\\", "_").strip()
        if not self.original_filename:
            raise ValidationError({"original_filename": "必须填写附件显示名称。"})

    @property
    def is_safe_image(self) -> bool:
        return bool(self.file and Path(self.file.name).suffix.lower().lstrip(".") in SAFE_IMAGE_EXTENSIONS)

    def save(self, *args, **kwargs):
        if self.file:
            self.original_filename = self.original_filename or Path(self.file.name).name
            self.file_size = getattr(self.file, "size", self.file_size)
            self.content_type = mimetypes.guess_type(self.file.name)[0] or "application/octet-stream"
            self.kind = AttachmentKind.IMAGE if self.is_safe_image else AttachmentKind.FILE
        super().save(*args, **kwargs)

    def __str__(self):
        return self.original_filename


class ForumTopicReadState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE, related_name="forum_topic_read_states", verbose_name="用户")
    topic = models.ForeignKey(ForumTopic, models.CASCADE, related_name="read_states", verbose_name="主题")
    last_viewed_at = models.DateTimeField("最后查看时间")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "topic"], name="unique_forum_topic_read_state")]
        verbose_name = "论坛主题阅读状态"
        verbose_name_plural = "论坛主题阅读状态"

    def __str__(self):
        return f"{self.user} - {self.topic}"


register_file_cleanup_signals(ForumPostAttachment, file_field="file")
