from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.forms import modelformset_factory
from django.utils import timezone
from django.utils.text import slugify

from core.constants import (
    WORLDSKILLS_FORUM_ATTACHMENT_MAX_COUNT,
    WORLDSKILLS_FORUM_ATTACHMENT_MAX_TOTAL_SIZE_MB,
)
from core.forms.fields import MultipleFileField
from core.uploads import WORLDSKILLS_FORUM_ATTACHMENT_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin

from .models import (
    AttachmentKind,
    ForumCategory,
    ForumModule,
    ForumPost,
    ForumPostAttachment,
    ForumTag,
    ForumTopic,
    SAFE_IMAGE_EXTENSIONS,
    SourceRole,
    http_url_validator,
)


TAG_SPLIT_PATTERN = re.compile(r"[,，;；\n]+")


def parse_external_attachment_urls(value: str) -> list[str]:
    urls = []
    for line in value.splitlines():
        url = line.strip()
        if not url:
            continue
        try:
            http_url_validator(url)
        except ValidationError as exc:
            raise ValidationError(f"附件来源链接无效：{url}") from exc
        urls.append(url)
    return list(dict.fromkeys(urls))


def external_attachment_defaults(url: str) -> dict[str, str]:
    filename = unquote(urlparse(url).path.rsplit("/", 1)[-1]).replace("/", "_").replace("\\", "_").strip()
    if not filename or filename in {".", ".."}:
        filename = "论坛外部附件"
    filename = filename[:255]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    kind = AttachmentKind.IMAGE if ext in SAFE_IMAGE_EXTENSIONS else AttachmentKind.FILE
    return {"original_filename": filename, "kind": kind}


def validate_attachment_capacity(post, files) -> None:
    existing = post.attachments.exclude(file="") if post and post.pk else ForumPostAttachment.objects.none()
    count = existing.count() + len(files)
    total_size = sum((size or 0) for size in existing.values_list("file_size", flat=True)) + sum(file.size for file in files)
    if count > WORLDSKILLS_FORUM_ATTACHMENT_MAX_COUNT:
        raise ValidationError(f"每个帖子最多归档 {WORLDSKILLS_FORUM_ATTACHMENT_MAX_COUNT} 个本地文件。")
    max_bytes = WORLDSKILLS_FORUM_ATTACHMENT_MAX_TOTAL_SIZE_MB * 1024 * 1024
    if total_size > max_bytes:
        raise ValidationError(f"每个帖子归档文件累计不能超过 {WORLDSKILLS_FORUM_ATTACHMENT_MAX_TOTAL_SIZE_MB}MB。")


def parse_tag_names(value: str) -> list[str]:
    names = []
    seen = set()
    for raw_name in TAG_SPLIT_PATTERN.split(value):
        name = raw_name.strip()
        if not name:
            continue
        if len(name) > 100:
            raise ValidationError(f"标签“{name[:20]}……”不能超过 100 个字符。")
        normalized = name.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        names.append(name)
    return names


def get_or_create_forum_tag(name: str) -> ForumTag:
    existing = ForumTag.objects.filter(name__iexact=name).order_by("pk").first()
    if existing:
        return existing

    base_slug = slugify(name, allow_unicode=True) or "tag"
    slug = base_slug
    suffix = 2
    while ForumTag.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    tag = ForumTag(name=name, slug=slug)
    tag.full_clean()
    tag.save()
    return tag


class ForumTopicForm(StyledFormMixin, forms.ModelForm):
    tags_text = forms.CharField(
        label="标签",
        required=False,
        help_text="直接输入标签；多个标签可使用逗号、分号或换行分隔。",
        widget=forms.TextInput(attrs={"placeholder": "例如：Linux，评分，竞赛规则"}),
    )

    class Meta:
        model = ForumTopic
        fields = [
            "competition_year", "translated_title", "original_title", "source_url",
            "source_topic_id", "summary", "module", "category", "status", "importance",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category_filter = Q(is_active=True)
        module_filter = Q(is_active=True)
        if self.instance.pk:
            category_filter |= Q(pk=self.instance.category_id)
            module_filter |= Q(pk=self.instance.module_id)
        self.fields["category"].queryset = ForumCategory.objects.filter(category_filter)
        self.fields["module"].queryset = ForumModule.objects.filter(module_filter)
        self.order_fields([
            "competition_year", "translated_title", "original_title", "source_url",
            "source_topic_id", "summary", "module", "category", "tags_text",
            "status", "importance",
        ])
        if not self.instance.pk:
            self.fields["competition_year"].initial = timezone.localdate().year
            general_module = ForumModule.objects.filter(is_active=True, slug="general").first()
            if general_module:
                self.fields["module"].initial = general_module
        else:
            self.fields["tags_text"].initial = "，".join(
                self.instance.tags.order_by("name", "pk").values_list("name", flat=True)
            )
        self.fields["translated_title"].help_text = "使用便于内部人员快速理解的中文标题。"
        self.fields["original_title"].help_text = "保留世界技能论坛中的原始标题。"
        self.fields["summary"].help_text = "填写当前结论或讨论状态，不要重复第一条帖子的翻译。"

    def clean_tags_text(self):
        value = self.cleaned_data.get("tags_text", "")
        self.cleaned_tag_names = parse_tag_names(value)
        return "，".join(self.cleaned_tag_names)

    def _save_tags(self, instance):
        tags = [get_or_create_forum_tag(name) for name in getattr(self, "cleaned_tag_names", [])]
        instance.tags.set(tags)

    def save(self, commit=True):
        if commit:
            with transaction.atomic():
                instance = super().save(commit=True)
                self._save_tags(instance)
            return instance

        instance = super().save(commit=False)
        original_save_m2m = self.save_m2m

        def save_m2m():
            original_save_m2m()
            self._save_tags(instance)

        self.save_m2m = save_m2m
        return instance


class ForumPostTranslationForm(StyledFormMixin, forms.Form):
    author_name = forms.CharField(label="原作者", max_length=200)
    source_role = forms.ChoiceField(label="来源身份", choices=ForumPost._meta.get_field("source_role").choices)
    source_role_detail = forms.CharField(label="其他身份说明", max_length=200, required=False)
    posted_at = forms.DateTimeField(label="论坛原始发布时间", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"), input_formats=["%Y-%m-%dT%H:%M"])
    source_url = forms.URLField(label="原帖链接", max_length=1000, required=False, validators=[http_url_validator], help_text="没有单条帖子链接时可留空，详情页将使用论坛主题链接。")
    source_post_id = forms.CharField(label="论坛帖子 ID", max_length=120, required=False)
    post_type = forms.ChoiceField(label="信息类型", choices=ForumPost._meta.get_field("post_type").choices)
    importance = forms.ChoiceField(label="重要程度", choices=ForumPost._meta.get_field("importance").choices)
    original_content = forms.CharField(label="英文原文", widget=forms.Textarea(attrs={"rows": 12}), help_text="完整粘贴英文原文。")
    translated_content = forms.CharField(label="中文翻译", widget=forms.Textarea(attrs={"rows": 12}), help_text="保存后直接发布，不经过审核。")
    attachments = MultipleFileField(label="本地归档文件", upload_spec=WORLDSKILLS_FORUM_ATTACHMENT_UPLOAD_SPEC, required=False)
    attachment_source_urls = forms.CharField(label="外部附件来源", required=False, widget=forms.Textarea(attrs={"rows": 4}), help_text="每行一个 HTTP/HTTPS URL；系统只记录链接，不会自动下载。")

    def __init__(self, *args, post=None, topic=None, include_attachments=True, **kwargs):
        self.post = post
        self.topic = topic or getattr(post, "topic", None)
        super().__init__(*args, **kwargs)
        if post and not self.is_bound:
            for name in ["author_name", "source_role", "source_role_detail", "posted_at", "source_url", "source_post_id", "post_type", "importance", "original_content"]:
                self.fields[name].initial = getattr(post, name)
            self.fields["translated_content"].initial = post.translation.translated_content
        elif not self.is_bound:
            self.fields["posted_at"].initial = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        if not include_attachments:
            self.fields.pop("attachments", None)
            self.fields.pop("attachment_source_urls", None)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("source_role") != SourceRole.OTHER:
            cleaned["source_role_detail"] = ""
        source_post_id = cleaned.get("source_post_id")
        if source_post_id and self.topic:
            duplicate = ForumPost.objects.filter(topic=self.topic, source_post_id=source_post_id)
            if self.post:
                duplicate = duplicate.exclude(pk=self.post.pk)
            if duplicate.exists():
                self.add_error("source_post_id", "该主题内已存在相同的论坛帖子 ID。")
        files = cleaned.get("attachments", [])
        validate_attachment_capacity(self.post, files)
        cleaned["external_attachment_urls"] = parse_external_attachment_urls(cleaned.get("attachment_source_urls", ""))
        return cleaned

    def post_data(self):
        names = ["author_name", "source_role", "source_role_detail", "posted_at", "source_url", "source_post_id", "post_type", "importance", "original_content"]
        return {name: self.cleaned_data[name] for name in names}

    def translation_data(self):
        return {"translated_content": self.cleaned_data["translated_content"]}


class AttachmentAddForm(StyledFormMixin, forms.Form):
    attachments = MultipleFileField(label="新增本地归档文件", upload_spec=WORLDSKILLS_FORUM_ATTACHMENT_UPLOAD_SPEC, required=False)
    attachment_source_urls = forms.CharField(label="新增外部附件来源", required=False, widget=forms.Textarea(attrs={"rows": 4}), help_text="每行一个 HTTP/HTTPS URL。")

    def __init__(self, *args, post=None, **kwargs):
        self.post = post
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        files = cleaned.get("attachments", [])
        urls = parse_external_attachment_urls(cleaned.get("attachment_source_urls", ""))
        if not files and not urls:
            raise ValidationError("请选择本地文件或填写至少一个外部附件来源链接。")
        validate_attachment_capacity(self.post, files)
        cleaned["external_attachment_urls"] = urls
        return cleaned


class AttachmentMetadataForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ForumPostAttachment
        fields = ["original_filename", "kind", "source_url", "caption_zh", "sort_order"]


AttachmentMetadataFormSet = modelformset_factory(ForumPostAttachment, form=AttachmentMetadataForm, extra=0)
