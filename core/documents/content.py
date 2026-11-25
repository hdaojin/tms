import re
from io import BytesIO

from bs4 import BeautifulSoup
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from .markdown import CONTENT_MARKDOWN_EXTRAS, DOCUMENT_HTML_CLEANER, render_content_markdown

from .limits import (
    MAX_CONTENT_BYTES,
    MAX_HTML_DEPTH,
    MAX_HTML_NODES,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_TOTAL_BYTES,
    MAX_IMAGE_TOTAL_PIXELS,
    MAX_METADATA_LENGTH,
)
from .types import DocumentAsset, DocumentError, DocumentInput
from .svg import SVG_MIME, normalize_svg

MARKDOWN_EXTRAS = tuple(extra for extra in CONTENT_MARKDOWN_EXTRAS if extra != "metadata")
ASSET_ID = re.compile(r"[a-zA-Z0-9_-]{1,64}")
IMAGE_FORMATS = {
    "image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP",
    "image/gif": "GIF", "image/bmp": "BMP", "image/tiff": "TIFF", "image/avif": "AVIF",
    "image/heic": "HEIF", "image/heif": "HEIF", "image/x-icon": "ICO",
}
CLEANER = DOCUMENT_HTML_CLEANER
register_heif_opener(thumbnails=False, depth_images=False, decode_threads=1)


def normalize_document_image(asset: DocumentAsset, image_id: str) -> tuple[bytes, str, int]:
    if asset.media_type == SVG_MIME:
        return normalize_svg(asset.content, image_id)
    expected = IMAGE_FORMATS.get(asset.media_type)
    if not expected:
        raise DocumentError(f"图片「{image_id}」的格式不受支持。")
    try:
        with Image.open(BytesIO(asset.content), formats=(expected,)) as source:
            if source.format != expected:
                raise DocumentError(f"图片「{image_id}」的文件格式与声明不一致。")
            pixels = source.width * source.height
            if pixels > MAX_IMAGE_PIXELS:
                raise DocumentError(f"图片「{image_id}」的像素数超过限制。")
            source.load()
            oriented = ImageOps.exif_transpose(source)
            mode = "RGBA" if oriented.has_transparency_data else "RGB"
            normalized = oriented.convert(mode)
            normalized.info.clear()
            output = BytesIO()
            # Keep photographic assets compact. Lossless encoding preserves diagrams and transparency.
            output_format = "JPEG" if expected == "JPEG" else "PNG"
            normalized.save(output, format=output_format, quality=90)
    except DocumentError:
        raise
    except (OSError, ValueError, RuntimeError, SyntaxError, Image.DecompressionBombError) as exc:
        raise DocumentError(f"图片「{image_id}」无法解码或尺寸超过限制。") from exc
    result = output.getvalue()
    if len(result) > MAX_IMAGE_BYTES:
        raise DocumentError(f"图片「{image_id}」处理后超过 5 MiB。")
    return result, f"image/{output_format.lower()}", pixels


def prepare_content(document: DocumentInput, *, for_pdf: bool) -> tuple[BeautifulSoup, dict[str, tuple[bytes, str]]]:
    metadata = (document.title, document.subtitle, document.author, document.organization)
    if not isinstance(document.content, str) or any(not isinstance(value, str) for value in metadata):
        raise DocumentError("正文和文档元数据必须使用文本。")
    if not document.title.strip():
        raise DocumentError("请输入文档标题。")
    if any(len(value) > MAX_METADATA_LENGTH for value in metadata):
        raise DocumentError("标题、副标题、作者和单位各限 200 字。")
    if not document.content.strip():
        raise DocumentError("请输入文档正文。")
    if len(document.content) > MAX_CONTENT_BYTES:
        raise DocumentError("文档正文超过 1 MiB。")
    try:
        content_size = len(document.content.encode("utf-8"))
        for value in metadata:
            value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise DocumentError("正文或文档元数据包含无效的 Unicode 字符。") from exc
    if content_size > MAX_CONTENT_BYTES:
        raise DocumentError("文档正文超过 1 MiB。")
    if document.content_format == "markdown":
        try:
            html = render_content_markdown(document.content, strict=True, document_assets=True).html
        except Exception as exc:
            raise DocumentError("Markdown 正文转换失败。") from exc
    elif document.content_format == "html_fragment":
        html = document.content
    else:
        raise DocumentError("未知的文档正文格式。")

    if len(html.encode("utf-8")) > 4 * MAX_CONTENT_BYTES:
        raise DocumentError("转换后的正文超过大小限制。")
    soup = BeautifulSoup(CLEANER.clean(html), "html.parser")
    # Exported documents display all instructional material, including collapsed answers.
    for details in soup.find_all("details"):
        details["open"] = ""
    nodes = soup.find_all(limit=MAX_HTML_NODES + 1)
    if len(nodes) > MAX_HTML_NODES:
        raise DocumentError("正文包含过多 HTML 元素。")
    for node in nodes:
        if sum(1 for _ in node.parents) > MAX_HTML_DEPTH:
            raise DocumentError("正文的嵌套层级过深。")
        for attr in ("colspan", "rowspan", "start"):
            if node.has_attr(attr) and not re.fullmatch(r"[1-9][0-9]?", node[attr]):
                del node[attr]
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if re.fullmatch(r"#[^\s#]+", href):
            if not for_pdf:
                # A fragment-only URL inside srcdoc otherwise resolves against the embedding page.
                link["href"] = f"about:srcdoc{href}"
            continue
        if not for_pdf or not re.match(r"(?i)^(https?://|mailto:)[^\s]+$", href):
            del link["href"]

    images = _prepare_images(soup, document.assets)
    if not images and not soup.get_text(strip=True):
        raise DocumentError("清理后没有可导出的正文。")
    return soup, images


def _prepare_images(soup, assets):
    if any(not isinstance(asset, DocumentAsset) or not isinstance(asset.content, bytes) for asset in assets.values()):
        raise DocumentError("图片资源必须提供文件字节和媒体类型。")
    sizes = [len(asset.content) for asset in assets.values()]
    if any(size > MAX_IMAGE_BYTES for size in sizes) or sum(sizes) > MAX_IMAGE_TOTAL_BYTES:
        raise DocumentError("图片单张限 5 MiB，总量限 20 MiB。")

    images = {}
    total_bytes = total_pixels = 0
    for tag in soup.find_all("img"):
        src = tag.get("src", "")
        image_id = src.removeprefix("tms-asset:")
        if not src.startswith("tms-asset:") or not ASSET_ID.fullmatch(image_id):
            alt = tag.get("alt", "").strip()[:80]
            label = f"「{alt}」" if alt else ""
            raise DocumentError(f"图片{label}必须使用有效的 tms-asset: 引用。")
        if image_id not in assets:
            raise DocumentError(f"找不到图片「{image_id}」。")
        if src not in images:
            content, mime, pixels = normalize_document_image(assets[image_id], image_id)
            images[src] = (content, mime)
            total_pixels += pixels
        total_bytes += len(images[src][0])
        if total_pixels > MAX_IMAGE_TOTAL_PIXELS or total_bytes > MAX_IMAGE_TOTAL_BYTES:
            raise DocumentError("正文图片的总大小或像素数超过限制。")
    return images
