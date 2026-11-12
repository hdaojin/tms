import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

from core.uploads import UploadSpec

TEXT_EXTENSIONS = (
    "txt",
    "md",
    "log",
    "csv",
    "json",
    "yaml",
    "yml",
    "xml",
    "conf",
    "ini",
    "cfg",
    "py",
    "sh",
    "ps1",
    "js",
    "ts",
    "sql",
    "c",
    "cpp",
    "go",
    "java",
    "rb",
)
REFERENCE_SPEC = UploadSpec(("pdf", "docx", *TEXT_EXTENSIONS), 5)
IMAGE_SPEC = UploadSpec(("png", "jpg", "jpeg", "webp"), 5)
MAX_REFERENCE_TEXT = 12000


def read_reference(file):
    REFERENCE_SPEC.validate_file(file)
    extension = Path(file.name).suffix.lower().lstrip(".")
    content = file.read()
    if extension in TEXT_EXTENSIONS:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError("文本或代码文件须使用 UTF-8 编码。") from None
        if "\x00" in text:
            raise ValidationError("参考文件不是可读取的文本或代码。")
        text = text[:MAX_REFERENCE_TEXT]
    else:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "training.log_extract", extension],
                cwd=settings.BASE_DIR,
                input=content,
                capture_output=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ValidationError("提取参考文件超时或失败，请粘贴所需文字。") from None
        if result.returncode:
            raise ValidationError("无法读取参考文件，请检查格式或粘贴所需文字。")
        text = result.stdout.decode("utf-8")
    if not text.strip():
        raise ValidationError("参考文件没有可提取的文字，请粘贴所需内容。")
    return text


def image_asset(file):
    from core.documents.types import DocumentAsset

    extension = Path(file.name).suffix.lower().lstrip(".")
    mime = "image/jpeg" if extension in {"jpg", "jpeg"} else f"image/{extension}"
    limit = IMAGE_SPEC.max_size_mb * 1024 * 1024
    content = file.read(limit + 1)
    if len(content) > limit:
        raise ValidationError("过程图片超过单张大小限制。")
    return DocumentAsset(content, mime)
