from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator
from django.http import HttpResponse, JsonResponse
from django.utils.deconstruct import deconstructible

from core.constants import (
    BUSINESS_DOCUMENT_ALLOWED_EXTENSIONS,
    BUSINESS_DOCUMENT_UPLOAD_MAX_SIZE_MB,
    CONDUCT_ALLOWED_EXTENSIONS,
    CONDUCT_UPLOAD_MAX_SIZE_MB,
    DEFAULT_UPLOAD_MAX_SIZE_MB,
    FEEDBACK_ATTACHMENT_ALLOWED_EXTENSIONS,
    FEEDBACK_ATTACHMENT_UPLOAD_MAX_SIZE_MB,
    GLOSSARY_WORKBOOK_ALLOWED_EXTENSIONS,
    GLOSSARY_WORKBOOK_UPLOAD_MAX_SIZE_MB,
    NOTICE_ALLOWED_EXTENSIONS,
    NOTICE_UPLOAD_MAX_SIZE_MB,
    SCORING_RESULT_PACKAGE_ALLOWED_EXTENSIONS,
    SCORING_RESULT_PACKAGE_UPLOAD_MAX_SIZE_MB,
    SCORING_WORKBOOK_ALLOWED_EXTENSIONS,
    SCORING_WORKBOOK_UPLOAD_MAX_SIZE_MB,
    TRAINING_LOG_ALLOWED_EXTENSIONS,
    TRAINING_LOG_UPLOAD_MAX_SIZE_MB,
    WORLDSKILLS_FORUM_ATTACHMENT_ALLOWED_EXTENSIONS,
    WORLDSKILLS_FORUM_ATTACHMENT_UPLOAD_MAX_SIZE_MB,
)


SignatureMatcher = Callable[[bytes], bool]


PDF_SIGNATURE = b"%PDF-"
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
GZIP_SIGNATURE = b"\x1f\x8b"
BZIP2_SIGNATURE = b"BZh"
RAR_SIGNATURES = (b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00")
SEVEN_Z_SIGNATURE = b"7z\xbc\xaf\x27\x1c"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
GIF_SIGNATURES = (b"GIF87a", b"GIF89a")
WEBP_RIFF_SIGNATURE = b"RIFF"
WEBP_FORMAT_SIGNATURE = b"WEBP"
BMP_SIGNATURE = b"BM"
JSON_LEADING_BYTES = (b"{", b"[")


def _html_safe_text(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _html_error_items(errors: Iterable[str]) -> str:
    return "".join(f"<li>{_html_safe_text(error)}</li>" for error in errors)


def _normalize_extensions(extensions: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(str(ext).lower().lstrip(".") for ext in (extensions or ()) if str(ext).strip("."))


def _read_file_header(file: UploadedFile, size: int = 512) -> bytes:
    """读取文件头并尽量恢复文件指针。"""
    position: int | None = None
    try:
        position = file.tell()
    except (AttributeError, OSError):
        position = None

    try:
        file.seek(0)
        return file.read(size)
    finally:
        if position is not None:
            try:
                file.seek(position)
            except (AttributeError, OSError):
                pass


def compute_file_sha256(file) -> str:
    """计算文件 SHA256，并尽量恢复文件指针。"""
    position = None
    try:
        position = file.tell()
    except (AttributeError, OSError):
        pass
    digest = hashlib.sha256()
    try:
        file.seek(0)
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    finally:
        if position is not None:
            try:
                file.seek(position)
            except (AttributeError, OSError):
                pass
    return digest.hexdigest()


def _starts_with_any(header: bytes, signatures: Iterable[bytes]) -> bool:
    return any(header.startswith(signature) for signature in signatures)


def _is_pdf(header: bytes) -> bool:
    return header.startswith(PDF_SIGNATURE)


def _is_zip_based(header: bytes) -> bool:
    return _starts_with_any(header, ZIP_SIGNATURES)


def _is_legacy_office(header: bytes) -> bool:
    return header.startswith(OLE_SIGNATURE)


def _is_ooxml_or_zip(header: bytes) -> bool:
    return _is_zip_based(header)


def _is_jpeg(header: bytes) -> bool:
    return header.startswith(JPEG_SIGNATURE)


def _is_png(header: bytes) -> bool:
    return header.startswith(PNG_SIGNATURE)


def _is_gif(header: bytes) -> bool:
    return _starts_with_any(header, GIF_SIGNATURES)


def _is_webp(header: bytes) -> bool:
    return header.startswith(WEBP_RIFF_SIGNATURE) and header[8:12] == WEBP_FORMAT_SIGNATURE


def _is_gzip(header: bytes) -> bool:
    return header.startswith(GZIP_SIGNATURE)


def _is_bzip2(header: bytes) -> bool:
    return header.startswith(BZIP2_SIGNATURE)


def _is_rar(header: bytes) -> bool:
    return _starts_with_any(header, RAR_SIGNATURES)


def _is_7z(header: bytes) -> bool:
    return header.startswith(SEVEN_Z_SIGNATURE)


def _is_bmp(header: bytes) -> bool:
    return header.startswith(BMP_SIGNATURE)


def _is_json(header: bytes) -> bool:
    return header.lstrip().startswith(JSON_LEADING_BYTES)


FILE_SIGNATURE_MATCHERS: dict[str, tuple[SignatureMatcher, ...]] = {
    "pdf": (_is_pdf,),
    "doc": (_is_legacy_office,),
    "xls": (_is_legacy_office,),
    "ppt": (_is_legacy_office,),
    "docx": (_is_ooxml_or_zip,),
    "xlsx": (_is_ooxml_or_zip,),
    "pptx": (_is_ooxml_or_zip,),
    "zip": (_is_zip_based,),
    "gz": (_is_gzip,),
    "bz2": (_is_bzip2,),
    "rar": (_is_rar,),
    "7z": (_is_7z,),
    "jpg": (_is_jpeg,),
    "jpeg": (_is_jpeg,),
    "png": (_is_png,),
    "gif": (_is_gif,),
    "webp": (_is_webp,),
    "bmp": (_is_bmp,),
    "json": (_is_json,),
}


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
        return isinstance(other, UploadSizeValidator) and self.max_size_mb == other.max_size_mb


@deconstructible
class UploadSignatureValidator:
    """基于常见文件头的轻量内容签名校验器。"""

    def __call__(self, file: UploadedFile) -> None:
        ext = Path(file.name or "").suffix.lower().lstrip(".")
        matchers = FILE_SIGNATURE_MATCHERS.get(ext)
        if not matchers:
            return

        header = _read_file_header(file)
        if not header:
            return

        if not any(matcher(header) for matcher in matchers):
            raise ValidationError(f"文件扩展名与实际文件类型不一致，请检查 {ext} 文件内容。")

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, UploadSignatureValidator)


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
        attrs.setdefault("data-upload-max-size-mb", str(self.max_size_mb))
        return attrs

    def help_text(self, action_text: str = "上传文件") -> str:
        return f"{action_text}，支持 {self.extensions_display}，大小不超过 {self.max_size_mb}MB。"

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
        UploadSignatureValidator()(file)


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
            error_html = _html_error_items(errors)
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


NOTICE_ATTACHMENT_UPLOAD_SPEC = UploadSpec(
    NOTICE_ALLOWED_EXTENSIONS,
    NOTICE_UPLOAD_MAX_SIZE_MB,
)
CONDUCT_ATTACHMENT_UPLOAD_SPEC = UploadSpec(
    CONDUCT_ALLOWED_EXTENSIONS,
    CONDUCT_UPLOAD_MAX_SIZE_MB,
)
MEETING_FILE_UPLOAD_SPEC = UploadSpec(["pdf"], DEFAULT_UPLOAD_MAX_SIZE_MB)
BUSINESS_DOCUMENT_UPLOAD_SPEC = UploadSpec(
    BUSINESS_DOCUMENT_ALLOWED_EXTENSIONS,
    BUSINESS_DOCUMENT_UPLOAD_MAX_SIZE_MB,
)
ASSESSMENT_DOCUMENT_UPLOAD_SPEC = BUSINESS_DOCUMENT_UPLOAD_SPEC
TRAINING_ATTACHMENT_UPLOAD_SPEC = BUSINESS_DOCUMENT_UPLOAD_SPEC
SCORING_WORKBOOK_UPLOAD_SPEC = UploadSpec(
    SCORING_WORKBOOK_ALLOWED_EXTENSIONS,
    SCORING_WORKBOOK_UPLOAD_MAX_SIZE_MB,
)
SCORING_RESULT_PACKAGE_UPLOAD_SPEC = UploadSpec(
    SCORING_RESULT_PACKAGE_ALLOWED_EXTENSIONS,
    SCORING_RESULT_PACKAGE_UPLOAD_MAX_SIZE_MB,
)
GLOSSARY_WORKBOOK_UPLOAD_SPEC = UploadSpec(
    GLOSSARY_WORKBOOK_ALLOWED_EXTENSIONS,
    GLOSSARY_WORKBOOK_UPLOAD_MAX_SIZE_MB,
)
TRAINING_LOG_UPLOAD_SPEC = UploadSpec(
    TRAINING_LOG_ALLOWED_EXTENSIONS,
    TRAINING_LOG_UPLOAD_MAX_SIZE_MB,
)
WORLDSKILLS_FORUM_ATTACHMENT_UPLOAD_SPEC = UploadSpec(
    WORLDSKILLS_FORUM_ATTACHMENT_ALLOWED_EXTENSIONS,
    WORLDSKILLS_FORUM_ATTACHMENT_UPLOAD_MAX_SIZE_MB,
)
FEEDBACK_ATTACHMENT_UPLOAD_SPEC = UploadSpec(
    FEEDBACK_ATTACHMENT_ALLOWED_EXTENSIONS,
    FEEDBACK_ATTACHMENT_UPLOAD_MAX_SIZE_MB,
)
