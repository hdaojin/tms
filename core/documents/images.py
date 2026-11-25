import hashlib

from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError

from .content import normalize_document_image
from .limits import MAX_IMAGE_BYTES, MAX_IMAGE_TOTAL_BYTES, MAX_IMAGE_TOTAL_PIXELS
from .types import DocumentAsset, DocumentError
from .markdown import render_content_markdown


FORMATS = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".svg": "image/svg+xml", ".gif": "image/gif", ".bmp": "image/bmp", ".avif": "image/avif",
    ".tif": "image/tiff", ".tiff": "image/tiff",
    ".heic": "image/heic", ".heif": "image/heif", ".ico": "image/x-icon",
    ".jpe": "image/jpeg", ".jfif": "image/jpeg",
}


class DocumentImages:
    """Collect authorized images within the shared document resource limits."""

    def __init__(self, *, reserved_bytes=0, reserved_pixels=0):
        self.reserved_bytes = reserved_bytes
        self.reserved_pixels = reserved_pixels
        self.assets = {}
        self.cache = {}
        self.size = self.pixels = 0

    def collect(self, sections, resolve_image, issues):
        refs, links = {}, {}
        for markdown in sections:
            if "![" not in markdown and "<img" not in markdown.lower():
                continue
            rendered = render_content_markdown(markdown, strict=True)
            for image in BeautifulSoup(rendered.html, "html.parser").find_all("img", src=True):
                src = image["src"]
                caption = str(image.get("alt") or "文档插图")[:80]
                try:
                    location = resolve_image(src)
                    if location is None:
                        continue
                    path, fallback_url = location
                    if path.suffix.lower() not in FORMATS:
                        issues.append(f"「{caption}」的格式暂不支持嵌入。")
                        continue
                    if path not in self.cache:
                        with path.open("rb") as file:
                            content = file.read(MAX_IMAGE_BYTES + 1)
                        if len(content) > MAX_IMAGE_BYTES:
                            raise DocumentError("图片超过 5 MiB。")
                        data, mime, pixels = normalize_document_image(
                            DocumentAsset(content, FORMATS[path.suffix.lower()]), caption
                        )
                        digest = hashlib.sha256(data).hexdigest()
                        self.cache[path] = (digest, DocumentAsset(data, mime), pixels)
                    digest, asset, pixels = self.cache[path]
                    if (
                        self.size + len(asset.content) > MAX_IMAGE_TOTAL_BYTES - self.reserved_bytes
                        or self.pixels + pixels > MAX_IMAGE_TOTAL_PIXELS - self.reserved_pixels
                    ):
                        raise ValidationError("文档插图总大小或总像素超过限制，请精简后重试。")
                    self.size += len(asset.content)
                    self.pixels += pixels
                    self.assets.setdefault(digest, (asset, caption))
                    refs[src] = digest
                except DocumentError as exc:
                    if path.suffix.lower() == ".svg":
                        links[src] = fallback_url
                    issues.append(f"「{caption}」仅保留图注：{exc}")
                except (OSError, ValueError, RuntimeError):
                    issues.append(f"「{caption}」无法在授权范围内安全读取，仅保留图注。")
        return refs, links
