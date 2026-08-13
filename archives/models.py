from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from core.uploads import PrivateMediaStorage, UploadSpec


archive_storage = PrivateMediaStorage("archives")
ARCHIVE_ASSET_UPLOAD_SPEC = UploadSpec(
    [
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "zip",
        "gz",
        "bz2",
        "rar",
        "7z",
        "json",
        "txt",
        "csv",
        "png",
        "jpg",
        "jpeg",
    ],
    settings.UPLOAD_MAX_SIZE_MB,
)


def calculate_file_sha256(file_obj):
    position = None
    try:
        position = file_obj.tell()
    except (AttributeError, OSError):
        position = None

    try:
        file_obj.seek(0)
    except (AttributeError, OSError):
        pass

    digest = hashlib.sha256()
    chunks = file_obj.chunks() if hasattr(file_obj, "chunks") else iter(lambda: file_obj.read(1024 * 1024), b"")
    for chunk in chunks:
        digest.update(chunk)

    if position is not None:
        try:
            file_obj.seek(position)
        except (AttributeError, OSError):
            pass
    return digest.hexdigest()


def archive_asset_upload_path(instance, filename):
    business_date = instance.business_date or timezone.localdate()
    asset_type = instance.asset_type or ArchiveAsset.AssetType.OTHER
    target = "unbound"
    if instance.target_content_type_id and instance.target_object_id:
        target = f"{instance.target_content_type.app_label}-{instance.target_content_type.model}-{instance.target_object_id}"
    return str(PurePosixPath(asset_type) / business_date.strftime("%Y/%m") / target / filename)


class ArchiveAsset(models.Model):
    class AssetType(models.TextChoices):
        TEST_PROJECT = "test_project", "试题"
        MARKING_SCHEME = "marking_scheme", "评分表"
        MARKING_STANDARD = "marking_standard", "评分标准"
        SCORING_SCRIPT = "scoring_script", "评分脚本"
        RESULT_PACKAGE = "result_package", "结果包"
        SCORE_SHEET = "score_sheet", "成绩表"
        TRAINING_LOG = "training_log", "训练日志"
        MEETING_RECORD = "meeting_record", "会议记录"
        LEARNING_RESOURCE = "learning_resource", "学习资料"
        ATTACHMENT = "attachment", "附件"
        OTHER = "other", "其他"

    target_content_type = models.ForeignKey(
        ContentType,
        verbose_name="绑定对象类型",
        on_delete=models.SET_NULL,
        related_name="archive_assets",
        null=True,
        blank=True,
    )
    target_object_id = models.PositiveBigIntegerField("绑定对象 ID", null=True, blank=True)
    target_object = GenericForeignKey("target_content_type", "target_object_id")
    skill_project = models.ForeignKey(
        "standards.SkillProject",
        verbose_name="技能项目",
        on_delete=models.PROTECT,
        related_name="archive_assets",
        null=True,
        blank=True,
    )
    asset_type = models.CharField("资料类型", max_length=40, choices=AssetType.choices, default=AssetType.OTHER)
    title = models.CharField("标题", max_length=200)
    description = models.TextField("描述", blank=True)
    file = models.FileField(
        "文件",
        storage=archive_storage,
        upload_to=archive_asset_upload_path,
        validators=ARCHIVE_ASSET_UPLOAD_SPEC.validators(),
        help_text=ARCHIVE_ASSET_UPLOAD_SPEC.help_text("上传资料文件"),
    )
    original_filename = models.CharField("原始文件名", max_length=255, blank=True)
    file_sha256 = models.CharField("文件 SHA256", max_length=64, blank=True, db_index=True)
    business_date = models.DateField("业务日期", default=timezone.localdate, db_index=True)
    source_system = models.CharField("来源系统", max_length=100, blank=True)
    source_external_id = models.CharField("外部 ID", max_length=150, blank=True)
    metadata = models.JSONField("元数据", default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传者",
        on_delete=models.SET_NULL,
        related_name="archive_assets",
        null=True,
        blank=True,
    )
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)
    is_locked = models.BooleanField("已锁定", default=False)

    class Meta:
        verbose_name = "资料资产"
        verbose_name_plural = "资料资产"
        ordering = ["-business_date", "-uploaded_at", "-pk"]

    @property
    def filename(self):
        if self.original_filename:
            return self.original_filename
        return PurePosixPath(self.file.name).name if self.file else ""

    @property
    def sha256_short(self):
        return self.file_sha256[:12] if self.file_sha256 else ""

    @property
    def bound_object_label(self):
        if self.target_object is None:
            return "-"
        return str(self.target_object)

    def _should_recalculate_hash(self, update_fields=None):
        if not self.file:
            return False
        if self._state.adding or not self.file_sha256:
            return True
        if update_fields is not None and "file" not in update_fields:
            return False
        return not getattr(self.file, "_committed", True)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        missing_original_filename = bool(self.file and not self.original_filename)
        if self.file:
            if not self.original_filename:
                self.original_filename = PurePosixPath(self.file.name).name
        should_recalculate_hash = self._should_recalculate_hash(update_fields)
        if should_recalculate_hash:
            self.file_sha256 = calculate_file_sha256(self.file)
        if update_fields is not None and (should_recalculate_hash or missing_original_filename):
            fields = set(update_fields)
            if should_recalculate_hash:
                fields.add("file_sha256")
            if missing_original_filename:
                fields.add("original_filename")
            kwargs["update_fields"] = fields
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

# Create your models here.
