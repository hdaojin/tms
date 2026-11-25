import html
import re
import uuid

from bs4 import BeautifulSoup

from core.utils.markdown import DEFAULT_MARKDOWN_EXTRAS, render_markdown_text

from .html import markdown_cleaner


class MarkdownDetailsError(ValueError):
    """讲义中的 details 折叠块结构不完整或发生嵌套。"""


class MarkdownRenderError(ValueError):
    """笔记正文未能完成 Markdown 渲染。"""


CONTENT_MARKDOWN_EXTRAS = (*DEFAULT_MARKDOWN_EXTRAS, "mermaid")
DETAILS_BODY_EXTRAS = tuple(
    extra for extra in CONTENT_MARKDOWN_EXTRAS if extra not in {"metadata", "toc"}
)

_DETAILS_LINE_RE = re.compile(
    r"[ \t]*<(?P<closing>/?)details\b(?P<attrs>[^>]*)>[ \t]*",
    re.IGNORECASE,
)
_SUMMARY_RE = re.compile(
    r"\A\s*<summary(?:\s[^>]*)?>(?P<label>.*?)</summary>\s*",
    re.IGNORECASE | re.DOTALL,
)
_FENCE_START_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})")
_OPEN_ATTRIBUTE_RE = re.compile(
    r"(?:^|\s)open(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s]+))?(?=\s|$)",
    re.IGNORECASE,
)


def _details_tags_outside_fences(content: str) -> list[tuple[int, int, bool, str]]:
    """返回 fenced code 之外独占一行的 details 标签。"""

    tags: list[tuple[int, int, bool, str]] = []
    offset = 0
    fence_character = ""
    fence_length = 0
    for line in content.splitlines(keepends=True):
        line_without_ending = line.rstrip("\r\n")
        fence_match = _FENCE_START_RE.match(line_without_ending)
        if fence_character:
            stripped = line_without_ending.lstrip()
            if re.fullmatch(rf"{re.escape(fence_character)}{{{fence_length},}}[ \t]*", stripped):
                fence_character = ""
                fence_length = 0
            offset += len(line)
            continue
        if fence_match:
            fence = fence_match.group("fence")
            fence_character = fence[0]
            fence_length = len(fence)
            offset += len(line)
            continue

        tag_match = _DETAILS_LINE_RE.fullmatch(line_without_ending)
        if tag_match:
            tags.append(
                (
                    offset,
                    offset + len(line_without_ending),
                    bool(tag_match.group("closing")),
                    tag_match.group("attrs"),
                )
            )
        offset += len(line)
    return tags


def _summary_text(summary_markup: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except Exception:  # pragma: no cover
        return re.sub(r"<[^>]+>", "", summary_markup).strip()
    return BeautifulSoup(summary_markup, "html.parser").get_text(" ", strip=True)


def _render_details_block(inner: str, attrs: str) -> str:
    summary_match = _SUMMARY_RE.match(inner)
    if summary_match is None:
        raise MarkdownDetailsError("每个 <details> 必须以完整的 <summary> 开头")

    summary = _summary_text(summary_match.group("label"))
    if not summary:
        raise MarkdownDetailsError("<summary> 不能为空")

    body = inner[summary_match.end() :].strip("\r\n")
    rendered_body = render_markdown_text(
        body,
        extensions=DETAILS_BODY_EXTRAS,
        lower_meta_keys=False,
    )
    if rendered_body.failed:
        raise MarkdownRenderError
    open_attribute = " open" if _OPEN_ATTRIBUTE_RE.search(attrs) else ""
    return (
        '<details class="note-details collapse collapse-arrow border border-base-300 '
        f'bg-base-100"{open_attribute}>'
        f'<summary class="collapse-title font-semibold">{html.escape(summary)}</summary>'
        f'<div class="collapse-content">{rendered_body.html}</div>'
        "</details>"
    )


def _extract_details_blocks(content: str) -> tuple[str, dict[str, str]]:
    """把合法 details 块替换为占位符，以便独立渲染其 Markdown 正文。"""

    tags = _details_tags_outside_fences(content)
    if not tags:
        return content, {}

    blocks: list[tuple[int, int, str, str]] = []
    opening: tuple[int, int, str] | None = None
    for start, end, is_closing, attrs in tags:
        if is_closing:
            if attrs.strip():
                raise MarkdownDetailsError("</details> 结束标签不能包含属性")
            if opening is None:
                raise MarkdownDetailsError("发现没有对应开始标签的 </details>")
            opening_start, opening_end, opening_attrs = opening
            blocks.append((opening_start, end, content[opening_end:start], opening_attrs))
            opening = None
            continue
        if opening is not None:
            raise MarkdownDetailsError("不支持嵌套 <details>")
        opening = (start, end, attrs)
    if opening is not None:
        raise MarkdownDetailsError("<details> 缺少结束标签")

    replacements: dict[str, str] = {}
    pieces: list[str] = []
    cursor = 0
    token_prefix = f"note-details-{uuid.uuid4().hex}"
    for index, (start, end, inner, attrs) in enumerate(blocks):
        token = f"{token_prefix}-{index}"
        replacements[token] = _render_details_block(inner, attrs)
        pieces.append(content[cursor:start])
        pieces.append(f'\n<div data-note-details-placeholder="{token}"></div>\n')
        cursor = end
    pieces.append(content[cursor:])
    return "".join(pieces), replacements


def _restore_details(rendered_html, details_blocks):
    soup = BeautifulSoup(rendered_html, "lxml")
    root = soup.body or soup
    for placeholder in list(root.find_all(attrs={"data-note-details-placeholder": True})):
        token = placeholder.get("data-note-details-placeholder")
        block_html = details_blocks.get(token) if isinstance(token, str) else None
        if block_html is None:
            placeholder.decompose()
            continue
        fragment = BeautifulSoup(block_html, "html.parser").find("details")
        if fragment is not None:
            placeholder.replace_with(fragment)

    for diagram in root.select("[data-mermaid-diagram]"):
        del diagram["data-mermaid-diagram"]
    for diagram in root.select("pre.mermaid-pre > div.mermaid"):
        diagram["data-mermaid-diagram"] = ""
    merged_html = root.decode_contents() if root is soup.body else str(root)
    return merged_html

def render_content_markdown(
    content, *, html_postprocessor=None, strict=False, document_assets=False, metadata=False,
):
    """Render shared document content. Resource authorization belongs to the caller."""
    prepared, details = _extract_details_blocks(content)

    def postprocess(rendered_html):
        merged = _restore_details(rendered_html, details)
        if html_postprocessor is not None:
            merged = html_postprocessor(merged)
        cleaner = DOCUMENT_HTML_CLEANER if document_assets else CONTENT_HTML_CLEANER
        return cleaner.clean(merged)

    extensions = CONTENT_MARKDOWN_EXTRAS if metadata else tuple(
        extra for extra in CONTENT_MARKDOWN_EXTRAS if extra != "metadata"
    )
    return render_markdown_text(
        prepared, extensions=extensions,
        html_postprocessor=postprocess, strict=strict,
    )


CONTENT_HTML_CLEANER = markdown_cleaner()
DOCUMENT_HTML_CLEANER = markdown_cleaner(document_assets=True)
