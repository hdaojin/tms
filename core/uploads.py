from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator
from django.http import HttpResponse, JsonResponse
from django.utils.deconstruct import deconstructible

from core.constants import (
    ASSESSMENT_ATTACHMENT_ALLOWED_EXTENSIONS,
    ASSESSMENT_ATTACHMENT_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_MC_ALLOWED_EXTENSIONS,
    ASSESSMENT_MC_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_MS_ALLOWED_EXTENSIONS,
    ASSESSMENT_MS_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_MT_ALLOWED_EXTENSIONS,
    ASSESSMENT_MT_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_TP_ALLOWED_EXTENSIONS,
    ASSESSMENT_TP_UPLOAD_MAX_SIZE_MB,
    COMPETITION_ALLOWED_EXTENSIONS,
    CONDUCT_ALLOWED_EXTENSIONS,
    CONDUCT_UPLOAD_MAX_SIZE_MB,
    DEFAULT_UPLOAD_MAX_SIZE_MB,
    MARKING_RESULT_PACKAGE_ALLOWED_EXTENSIONS,
    MARKING_RESULT_PACKAGE_UPLOAD_MAX_SIZE_MB,
    MARKING_WORKBOOK_ALLOWED_EXTENSIONS,
    MARKING_WORKBOOK_UPLOAD_MAX_SIZE_MB,
    NOTICE_ALLOWED_EXTENSIONS,
    NOTICE_UPLOAD_MAX_SIZE_MB,
    TRAININGLOG_ALLOWED_EXTENSIONS,
    TRAININGLOG_UPLOAD_MAX_SIZE_MB,
)


def _normalize_extensions(extensions: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(
        str(ext).lower().lstrip(".")
        for ext in (extensions or ())
        if str(ext).strip(".")
    )


@deconstructible
class UploadSizeValidator:
    """可迁移的上传大小校验器。"""

    def __init__(self, max_size_mb: int = DEFAULT_UPLOAD_MAX_SIZE_MB):
        self.max_size_mb = int(max_size_mb)

    def __call__(self, file: UploadedFile) -> None:
        file_size = getattr(file, "size", 0)
        if file_size > self.max_size_mb * 1024 * 1024:
            raise ValidationError(f"上传文件大小不能超过 {self.max_size_mb}MB。")

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, UploadSizeValidator)
            and self.max_size_mb == other.max_size_mb
        )


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    """基于 settings.PRIVATE_MEDIA_ROOT 的私有文件存储。"""

    def __init__(self, subdir: str):
        self.subdir = str(subdir).strip("/\\")
        super().__init__()

    @property
    def base_location(self) -> str:
        return str(Path(settings.PRIVATE_MEDIA_ROOT) / self.subdir)

    @property
    def location(self) -> str:
        return os.path.abspath(self.base_location)

    def deconstruct(self):
        return ("core.uploads.PrivateMediaStorage", [self.subdir], {})

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, PrivateMediaStorage) and self.subdir == other.subdir


@dataclass(frozen=True)
class UploadSpec:
    allowed_extensions: Iterable[str]
    max_size_mb: int = DEFAULT_UPLOAD_MAX_SIZE_MB

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_extensions",
            _normalize_extensions(self.allowed_extensions),
        )
        object.__setattr__(self, "max_size_mb", int(self.max_size_mb))

    @property
    def accept(self) -> str:
        return ",".join(f".{ext}" for ext in self.allowed_extensions)

    @property
    def extensions_display(self) -> str:
        return ", ".join(self.allowed_extensions)

    def widget_attrs(self, **attrs: Any) -> dict[str, Any]:
        attrs.setdefault("accept", self.accept)
        return attrs

    def help_text(self, action_text: str = "上传文件") -> str:
        return (
            f"{action_text}，支持 {self.extensions_display}，"
            f"大小不超过 {self.max_size_mb}MB"
        )

    def validators(self) -> list[Any]:
        validators: list[Any] = []
        if self.allowed_extensions:
            validators.append(
                FileExtensionValidator(
                    allowed_extensions=self.allowed_extensions,
                    message=f"仅支持以下格式的文件：{self.extensions_display}",
                )
            )
        validators.append(UploadSizeValidator(self.max_size_mb))
        return validators

    def validate_file(self, file: UploadedFile) -> None:
        for validator in self.validators():
            validator(file)


class FileUploadMixin:
    """用于类视图的轻量文件上传处理 mixin。"""

    upload_field_name: str = "file"
    allowed_extensions: list[str] | None = None
    max_size_mb: int = DEFAULT_UPLOAD_MAX_SIZE_MB

    def get_upload_spec(self) -> UploadSpec:
        return UploadSpec(self.allowed_extensions or (), self.max_size_mb)

    def validate_file(self, file: UploadedFile) -> list[str]:
        try:
            self.get_upload_spec().validate_file(file)
        except ValidationError as exc:
            return list(exc.messages)
        return []

    def handle_uploaded_file(self, file: UploadedFile, request) -> Any:
        raise NotImplementedError("子类必须实现 handle_uploaded_file 方法")

    def get_success_response(self, result: Any, request) -> HttpResponse:
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<div class="alert alert-success">'
                '<span class="icon-[tabler--check] size-5"></span>'
                "<span>文件上传成功！</span>"
                "</div>"
            )
        return JsonResponse({"success": True, "message": "文件上传成功"})

    def get_error_response(self, errors: list[str], request) -> HttpResponse:
        if request.headers.get("HX-Request"):
            error_html = "".join(f"<li>{error}</li>" for error in errors)
            return HttpResponse(
                '<div class="alert alert-error">'
                '<span class="icon-[tabler--alert-circle] size-5"></span>'
                f'<ul class="list-disc list-inside">{error_html}</ul>'
                "</div>",
                status=400,
            )
        return JsonResponse({"success": False, "errors": errors}, status=400)

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist(self.upload_field_name)

        if not files:
            return self.get_error_response(["请选择要上传的文件"], request)

        all_errors = []
        results = []

        for file in files:
            errors = self.validate_file(file)
            if errors:
                all_errors.extend([f"「{file.name}」: {error}" for error in errors])
                continue

            try:
                result = self.handle_uploaded_file(file, request)
                results.append(result)
            except ValidationError as exc:
                all_errors.extend([f"「{file.name}」: {message}" for message in exc.messages])
            except Exception as exc:
                all_errors.append(f"「{file.name}」: 上传失败 - {exc}")

        if all_errors and not results:
            return self.get_error_response(all_errors, request)

        return self.get_success_response(results, request)


def validate_upload_file(
    file: UploadedFile,
    allowed_extensions: list[str] | None = None,
    max_size_mb: int = DEFAULT_UPLOAD_MAX_SIZE_MB,
) -> None:
    """验证单个上传文件。"""
    UploadSpec(allowed_extensions or (), max_size_mb).validate_file(file)


def get_file_icon_class(filename: str) -> str:
    """根据文件扩展名返回 Iconify 图标类。"""
    ext = Path(filename).suffix.lower().lstrip(".")
    icons = {
        "pdf": "icon-[tabler--file-type-pdf]",
        "doc": "icon-[tabler--file-type-doc]",
        "docx": "icon-[tabler--file-type-docx]",
        "xls": "icon-[tabler--file-type-xls]",
        "xlsx": "icon-[tabler--file-type-xls]",
        "ppt": "icon-[tabler--file-type-ppt]",
        "pptx": "icon-[tabler--file-type-ppt]",
        "txt": "icon-[tabler--file-type-txt]",
        "csv": "icon-[tabler--file-type-csv]",
        "zip": "icon-[tabler--file-zip]",
        "rar": "icon-[tabler--file-zip]",
        "7z": "icon-[tabler--file-zip]",
        "tar": "icon-[tabler--file-zip]",
        "gz": "icon-[tabler--file-zip]",
        "jpg": "icon-[tabler--photo]",
        "jpeg": "icon-[tabler--photo]",
        "png": "icon-[tabler--photo]",
        "gif": "icon-[tabler--photo]",
        "webp": "icon-[tabler--photo]",
        "mp4": "icon-[tabler--video]",
        "avi": "icon-[tabler--video]",
        "mkv": "icon-[tabler--video]",
        "mp3": "icon-[tabler--music]",
        "wav": "icon-[tabler--music]",
    }
    return icons.get(ext, "icon-[tabler--file]")


def is_image_file(filename: str) -> bool:
    """判断文件名是否为常见图片格式。"""
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"}


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.2f} MB"
    return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"


ASSESSMENT_TP_UPLOAD_SPEC = UploadSpec(
    ASSESSMENT_TP_ALLOWED_EXTENSIONS,
    ASSESSMENT_TP_UPLOAD_MAX_SIZE_MB,
)
ASSESSMENT_MC_UPLOAD_SPEC = UploadSpec(
    ASSESSMENT_MC_ALLOWED_EXTENSIONS,
    ASSESSMENT_MC_UPLOAD_MAX_SIZE_MB,
)
ASSESSMENT_MT_UPLOAD_SPEC = UploadSpec(
    ASSESSMENT_MT_ALLOWED_EXTENSIONS,
    ASSESSMENT_MT_UPLOAD_MAX_SIZE_MB,
)
ASSESSMENT_MS_UPLOAD_SPEC = UploadSpec(
    ASSESSMENT_MS_ALLOWED_EXTENSIONS,
    ASSESSMENT_MS_UPLOAD_MAX_SIZE_MB,
)
ASSESSMENT_ATTACHMENT_UPLOAD_SPEC = UploadSpec(
    ASSESSMENT_ATTACHMENT_ALLOWED_EXTENSIONS,
    ASSESSMENT_ATTACHMENT_UPLOAD_MAX_SIZE_MB,
)
NOTICE_ATTACHMENT_UPLOAD_SPEC = UploadSpec(
    NOTICE_ALLOWED_EXTENSIONS,
    NOTICE_UPLOAD_MAX_SIZE_MB,
)
TRAININGLOG_UPLOAD_SPEC = UploadSpec(
    TRAININGLOG_ALLOWED_EXTENSIONS,
    TRAININGLOG_UPLOAD_MAX_SIZE_MB,
)
CONDUCT_ATTACHMENT_UPLOAD_SPEC = UploadSpec(
    CONDUCT_ALLOWED_EXTENSIONS,
    CONDUCT_UPLOAD_MAX_SIZE_MB,
)
MEETING_FILE_UPLOAD_SPEC = UploadSpec(["pdf"], DEFAULT_UPLOAD_MAX_SIZE_MB)
COMPETITION_DOCUMENT_UPLOAD_SPEC = UploadSpec(
    COMPETITION_ALLOWED_EXTENSIONS,
    DEFAULT_UPLOAD_MAX_SIZE_MB,
)
MARKING_WORKBOOK_UPLOAD_SPEC = UploadSpec(
    MARKING_WORKBOOK_ALLOWED_EXTENSIONS,
    MARKING_WORKBOOK_UPLOAD_MAX_SIZE_MB,
)
MARKING_RESULT_PACKAGE_UPLOAD_SPEC = UploadSpec(
    MARKING_RESULT_PACKAGE_ALLOWED_EXTENSIONS,
    MARKING_RESULT_PACKAGE_UPLOAD_MAX_SIZE_MB,
)
