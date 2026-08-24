from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

from django.http import FileResponse, Http404

from core.uploads import FILE_SIGNATURE_MATCHERS


TEXT_PREVIEW_LIMIT_BYTES = 1024 * 1024
TEXT_PREVIEW_EXTENSIONS = frozenset({"txt", "md", "csv", "json", "yaml", "yml", "log"})


class FilePreviewKind(StrEnum):
    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class FilePreviewMetadata:
    label: str
    value: str


@dataclass(frozen=True)
class FilePreviewDescriptor:
    filename: str
    file_size: int | None
    type_label: str
    content_type: str | None
    preview_kind: FilePreviewKind
    download_url: str
    preview_url: str | None
    uploader_name: str
    uploaded_at: datetime | None
    source_label: str
    source_url: str
    title: str
    description: str
    metadata: tuple[FilePreviewMetadata, ...] = field(default_factory=tuple)
    text_content: str | None = None
    text_truncated: bool = False
    file_available: bool = True


_INLINE_FILE_TYPES = {
    "pdf": (FilePreviewKind.PDF, "application/pdf"),
    "jpg": (FilePreviewKind.IMAGE, "image/jpeg"),
    "jpeg": (FilePreviewKind.IMAGE, "image/jpeg"),
    "png": (FilePreviewKind.IMAGE, "image/png"),
    "gif": (FilePreviewKind.IMAGE, "image/gif"),
    "webp": (FilePreviewKind.IMAGE, "image/webp"),
}


def _extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def _open_file(file) -> BinaryIO:
    close_on_error = bool(getattr(file, "closed", True))
    opened = None
    try:
        opened = file.open("rb")
        opened.seek(0)
    except (FileNotFoundError, OSError, ValueError, AttributeError) as exc:
        if opened is not None and close_on_error:
            try:
                opened.close()
            except (OSError, ValueError):
                pass
        raise Http404("文件不存在。") from exc
    return opened


def _read_bytes(file, limit: int) -> bytes:
    was_closed = bool(getattr(file, "closed", True))
    opened = _open_file(file)
    try:
        return opened.read(limit)
    except (OSError, ValueError) as exc:
        raise Http404("文件无法读取。") from exc
    finally:
        try:
            opened.seek(0)
        except (OSError, ValueError):
            pass
        if was_closed:
            try:
                opened.close()
            except (OSError, ValueError):
                pass


def _verified_inline_type(file, filename: str) -> tuple[FilePreviewKind, str] | None:
    extension = _extension(filename)
    inline_type = _INLINE_FILE_TYPES.get(extension)
    matchers = FILE_SIGNATURE_MATCHERS.get(extension)
    if inline_type is None or not matchers:
        return None
    header = _read_bytes(file, 16)
    if not header or not any(matcher(header) for matcher in matchers):
        return None
    return inline_type


def _read_text_preview(file) -> tuple[str, bool] | None:
    content = _read_bytes(file, TEXT_PREVIEW_LIMIT_BYTES + 1)
    truncated = len(content) > TEXT_PREVIEW_LIMIT_BYTES
    preview_bytes = content[:TEXT_PREVIEW_LIMIT_BYTES]
    try:
        return preview_bytes.decode("utf-8-sig"), truncated
    except UnicodeDecodeError as exc:
        if (
            not truncated
            or exc.reason != "unexpected end of data"
            or exc.end != len(preview_bytes)
        ):
            return None
        return preview_bytes[: exc.start].decode("utf-8-sig"), True


def _file_size(file) -> tuple[int | None, bool]:
    try:
        return int(file.size), True
    except (FileNotFoundError, OSError, ValueError, TypeError, AttributeError):
        return None, False


def build_file_preview_descriptor(
    *,
    file,
    filename: str,
    download_url: str,
    preview_url: str | None,
    uploader_name: str,
    uploaded_at: datetime | None,
    source_label: str,
    source_url: str,
    title: str = "",
    description: str = "",
    metadata: tuple[FilePreviewMetadata, ...] = (),
) -> FilePreviewDescriptor:
    file_size, file_available = _file_size(file)
    extension = _extension(filename)
    type_label = extension.upper() if extension else "未知"
    preview_kind = FilePreviewKind.UNAVAILABLE
    content_type = None
    text_content = None
    text_truncated = False
    resolved_preview_url = None

    if file_available:
        try:
            inline_type = _verified_inline_type(file, filename)
            if inline_type is not None:
                preview_kind, content_type = inline_type
                resolved_preview_url = preview_url
            elif extension in TEXT_PREVIEW_EXTENSIONS:
                text_preview = _read_text_preview(file)
                if text_preview is not None:
                    text_content, text_truncated = text_preview
                    preview_kind = FilePreviewKind.TEXT
                    content_type = "text/plain; charset=utf-8"
        except Http404:
            file_available = False

    return FilePreviewDescriptor(
        filename=filename,
        file_size=file_size,
        type_label=type_label,
        content_type=content_type,
        preview_kind=preview_kind,
        download_url=download_url,
        preview_url=resolved_preview_url,
        uploader_name=uploader_name,
        uploaded_at=uploaded_at,
        source_label=source_label,
        source_url=source_url,
        title=title,
        description=description,
        metadata=metadata,
        text_content=text_content,
        text_truncated=text_truncated,
        file_available=file_available,
    )


def _apply_private_file_headers(response: FileResponse) -> FileResponse:
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def build_inline_preview_response(file, filename: str) -> FileResponse:
    inline_type = _verified_inline_type(file, filename)
    if inline_type is None:
        raise Http404("该文件不支持在线预览。")
    preview_kind, content_type = inline_type
    response = FileResponse(
        _open_file(file),
        as_attachment=False,
        filename=filename,
        content_type=content_type,
    )
    if preview_kind == FilePreviewKind.PDF:
        response["X-Frame-Options"] = "SAMEORIGIN"
    return _apply_private_file_headers(response)


def build_download_response(file, filename: str) -> FileResponse:
    response = FileResponse(_open_file(file), as_attachment=True, filename=filename)
    return _apply_private_file_headers(response)
