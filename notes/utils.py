from __future__ import annotations

import html
import re
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from core.utils.markdown import DEFAULT_MARKDOWN_EXTRAS, render_markdown_text

from .paths import (
    InvalidNotePathError,
    NoteNotFoundError,
    resolve_repo_relative_path,
)


@dataclass
class NoteContent:
    """渲染后的笔记内容与元数据容器。"""

    repo: str
    slug: str
    meta: dict[str, Any]
    html: str
    source_path: Path
    toc_tokens: str | None


@dataclass
class ReadmeNavigation:
    """README 目录区渲染结果及其线性笔记顺序。"""

    html: str
    items: list[dict[str, str]]


class NoteDetailsParseError(ValueError):
    """讲义中的 details 折叠块结构不完整或发生嵌套。"""


NOTE_MARKDOWN_EXTRAS = (*DEFAULT_MARKDOWN_EXTRAS, "mermaid")
NOTE_DETAILS_BODY_EXTRAS = tuple(
    extra for extra in NOTE_MARKDOWN_EXTRAS if extra not in {"metadata", "toc"}
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


def normalize_repo_name(repo: str) -> str:
    """校验 URL 中的稳定访问标识。"""

    if not repo or not re.fullmatch(r"[A-Za-z0-9_-]+", repo):
        raise InvalidNotePathError("Invalid repo name")
    return repo


def resolve_note_markdown_path(repo_root: Path, slug: str | None) -> Path:
    """把文档 slug 解析成已登记仓库根目录内的 Markdown 文件。"""

    def readme_or_raise() -> Path:
        candidate = repo_root / "README.md"
        resolved = candidate.resolve(strict=False)
        if resolved.is_relative_to(repo_root.resolve()) and resolved.is_file():
            return resolved
        raise NoteNotFoundError("README not found")

    if not slug:
        return readme_or_raise()

    decoded_slug = unquote(slug).replace("\\", "/")
    slug_path = PurePosixPath(decoded_slug)
    if slug_path.is_absolute() or ".." in slug_path.parts:
        raise InvalidNotePathError("Invalid slug path")

    normalized_slug = slug_path.as_posix().strip("/")
    if not normalized_slug:
        return readme_or_raise()
    if normalized_slug.lower().endswith(".md"):
        normalized_slug = normalized_slug[:-3]

    candidates = (f"{normalized_slug}.md", f"{normalized_slug}/README.md")
    for relative in candidates:
        _, candidate = resolve_repo_relative_path(repo_root, "", relative)
        if candidate.is_file():
            return candidate
    raise NoteNotFoundError("Note file not found")


def _is_external_url(url: str) -> bool:
    return url.lower().startswith(("http://", "https://", "//", "mailto:", "tel:", "ftp:", "data:"))


def _rewrite_url(url: str | None, repo: str, repo_root: Path, current_dir: str) -> str | None:
    if not url:
        return url
    if url.startswith(("#", "?", "/")) or _is_external_url(url):
        return url

    split = urlsplit(url)
    if split.scheme or split.netloc:
        return None
    if not split.path and (split.query or split.fragment):
        return url

    try:
        resolved_path, _ = resolve_repo_relative_path(repo_root, current_dir, split.path or "")
    except InvalidNotePathError:
        return None

    suffix = PurePosixPath(resolved_path).suffix.lower()
    first_segment = resolved_path.split("/", 1)[0] if resolved_path else ""
    is_assets_path = first_segment == "assets"
    if suffix in {".md", ""} and not is_assets_path:
        slug_path = resolved_path[:-3] if resolved_path.lower().endswith(".md") else resolved_path
        slug_path = slug_path.strip("/")
        target = f"/notes/{repo}/" if not slug_path else f"/notes/{repo}/{slug_path}/"
    else:
        target = f"/notes-files/{repo}/{resolved_path}"
    return urlunsplit(("", "", target, split.query, split.fragment))


def rewrite_relative_urls(
    html: str,
    repo: str,
    repo_root: Path,
    current_dir: str = "",
    *,
    omit_unsafe_list_items: bool = False,
) -> str:
    """改写仓库内链接，并移除任何逃逸配置根目录的链接目标。"""

    try:
        from bs4 import BeautifulSoup
    except Exception:  # pragma: no cover - dependency is required in production
        return html

    soup = BeautifulSoup(html, "lxml")
    root = soup.body or soup
    for tag in list(root.find_all(href=True)):
        href = tag.get("href")
        rewritten = _rewrite_url(href if isinstance(href, str) else None, repo, repo_root, current_dir)
        if rewritten is None:
            if omit_unsafe_list_items:
                list_item = tag.find_parent("li")
                if list_item is not None:
                    list_item.decompose()
                    continue
            tag.attrs.pop("href", None)
        else:
            tag["href"] = rewritten

    for tag in list(root.find_all(src=True)):
        src = tag.get("src")
        rewritten = _rewrite_url(src if isinstance(src, str) else None, repo, repo_root, current_dir)
        if rewritten is None:
            tag.attrs.pop("src", None)
        else:
            tag["src"] = rewritten

    return root.decode_contents() if root is soup.body else str(root)


def limit_navigation_depth(html: str | None, max_depth: int = 3) -> str:
    """保留导航列表的前 max_depth 层。"""

    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
    except Exception:  # pragma: no cover
        return html

    soup = BeautifulSoup(html, "lxml")
    root = soup.body or soup
    for nav_list in list(root.find_all(["ul", "ol"])):
        depth = len(nav_list.find_parents(["ul", "ol"])) + 1
        if depth > max_depth:
            nav_list.decompose()
    return root.decode_contents() if root is soup.body else str(root)


_TOC_START_RE = re.compile(r"^\s*<!--\s*(?:TOC|TOC_START)\s*-->\s*$", re.IGNORECASE)
_TOC_END_RE = re.compile(r"^\s*<!--\s*(?:/TOC|TOC_END)\s*-->\s*$", re.IGNORECASE)


def _extract_readme_toc(content: str) -> str:
    start_index: int | None = None
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if start_index is None:
            if _TOC_START_RE.fullmatch(line):
                start_index = index + 1
            continue
        if _TOC_END_RE.fullmatch(line):
            return "\n".join(lines[start_index:index])
    return ""


def get_readme_navigation(repo_root: Path, repo: str, max_depth: int = 3) -> ReadmeNavigation:
    """读取 README 的 TOC 区域，并生成层级 HTML 与深度优先线性顺序。"""

    readme_path = repo_root / "README.md"
    if not readme_path.is_file():
        return ReadmeNavigation(html="", items=[])
    try:
        segment = _extract_readme_toc(readme_path.read_text(encoding="utf-8"))
    except OSError:
        return ReadmeNavigation(html="", items=[])
    if not segment.strip():
        return ReadmeNavigation(html="", items=[])

    rendered = render_markdown_text(
        segment,
        extensions=("fenced-code-blocks", "tables", "header-ids", "break-on-newline", "smarty-pants"),
        lower_meta_keys=False,
    ).html
    rewritten = rewrite_relative_urls(
        rendered,
        repo,
        repo_root,
        current_dir="",
        omit_unsafe_list_items=True,
    )

    try:
        from bs4 import BeautifulSoup
    except Exception:  # pragma: no cover
        return ReadmeNavigation(html=limit_navigation_depth(rewritten, max_depth=max_depth), items=[])

    rewritten_soup = BeautifulSoup(rewritten, "lxml")
    rewritten_root = rewritten_soup.body or rewritten_soup
    note_prefix = f"/notes/{repo}/"
    asset_prefix = f"/notes-files/{repo}/"
    for anchor in list(rewritten_root.find_all("a", href=True)):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        split = urlsplit(href)
        try:
            if split.path.startswith(note_prefix):
                slug = split.path[len(note_prefix) :].strip("/")
                resolve_note_markdown_path(repo_root, slug or None)
            elif split.path.startswith(asset_prefix):
                relative = split.path[len(asset_prefix) :]
                _, target = resolve_repo_relative_path(repo_root, "", relative)
                if not target.is_file():
                    raise NoteNotFoundError("Navigation asset not found")
            else:
                continue
        except (InvalidNotePathError, NoteNotFoundError):
            list_item = anchor.find_parent("li")
            if list_item is not None:
                list_item.decompose()
            else:
                anchor.decompose()

    rewritten = rewritten_root.decode_contents() if rewritten_root is rewritten_soup.body else str(rewritten_root)
    navigation_html = limit_navigation_depth(rewritten, max_depth=max_depth)

    soup = BeautifulSoup(navigation_html, "lxml")
    items: list[dict[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        split = urlsplit(href)
        if not split.path.startswith(note_prefix):
            continue
        slug = split.path[len(note_prefix) :].strip("/")
        items.append({"slug": slug, "title": anchor.get_text(" ", strip=True)})
    return ReadmeNavigation(html=navigation_html, items=items)


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
        raise NoteDetailsParseError("每个 <details> 必须以完整的 <summary> 开头")

    summary = _summary_text(summary_match.group("label"))
    if not summary:
        raise NoteDetailsParseError("<summary> 不能为空")

    body = inner[summary_match.end() :].strip("\r\n")
    rendered_body = render_markdown_text(
        body,
        extensions=NOTE_DETAILS_BODY_EXTRAS,
        lower_meta_keys=False,
    ).html
    open_attribute = " open" if _OPEN_ATTRIBUTE_RE.search(attrs) else ""
    return (
        '<details class="note-details collapse collapse-arrow border border-base-300 '
        f'bg-base-100"{open_attribute}>'
        f'<summary class="collapse-title font-semibold">{html.escape(summary)}</summary>'
        f'<div class="collapse-content">{rendered_body}</div>'
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
                raise NoteDetailsParseError("</details> 结束标签不能包含属性")
            if opening is None:
                raise NoteDetailsParseError("发现没有对应开始标签的 </details>")
            opening_start, opening_end, opening_attrs = opening
            blocks.append((opening_start, end, content[opening_end:start], opening_attrs))
            opening = None
            continue
        if opening is not None:
            raise NoteDetailsParseError("不支持嵌套 <details>")
        opening = (start, end, attrs)
    if opening is not None:
        raise NoteDetailsParseError("<details> 缺少结束标签")

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


def _postprocess_note_html(
    rendered_html: str,
    details_blocks: dict[str, str],
    repo: str,
    repo_root: Path,
    current_dir: str,
) -> str:
    try:
        from bs4 import BeautifulSoup
    except Exception:  # pragma: no cover
        return rewrite_relative_urls(rendered_html, repo, repo_root, current_dir=current_dir)

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

    for diagram in root.select("pre.mermaid-pre > .mermaid"):
        diagram["data-mermaid-diagram"] = ""
    merged_html = root.decode_contents() if root is soup.body else str(root)
    return rewrite_relative_urls(merged_html, repo, repo_root, current_dir=current_dir)


def _render_details_parse_error(content: str, error: NoteDetailsParseError) -> str:
    escaped_source = html.escape(content, quote=False)
    return (
        '<div role="alert" class="alert alert-error mb-4">'
        f"<span>折叠内容解析失败：{html.escape(str(error))}</span>"
        "</div>"
        '<pre class="overflow-x-auto"><code>'
        f"{escaped_source}"
        "</code></pre>"
    )


def render_note_markdown(path: Path, repo: str, repo_root: Path, slug: str) -> NoteContent:
    """读取 Markdown，生成正文和最多三级的相对标题大纲。"""

    try:
        current_dir = path.parent.relative_to(repo_root).as_posix()
    except ValueError:
        raise InvalidNotePathError("Note path escaped repository root") from None

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        rendered_html = ""
        meta = {"_parse_error": True, "_parse_error_message": str(exc)}
        toc_html = ""
    else:
        try:
            preprocessed_content, details_blocks = _extract_details_blocks(content)
        except NoteDetailsParseError as exc:
            rendered_html = _render_details_parse_error(content, exc)
            meta = {"_parse_error": True, "_parse_error_message": str(exc)}
            toc_html = ""
        else:
            rendered = render_markdown_text(
                preprocessed_content,
                extensions=NOTE_MARKDOWN_EXTRAS,
                html_postprocessor=lambda rendered_html: _postprocess_note_html(
                    rendered_html,
                    details_blocks,
                    repo,
                    repo_root,
                    current_dir,
                ),
            )
            rendered_html = rendered.html
            meta = rendered.meta
            toc_html = limit_navigation_depth(rendered.toc, max_depth=3)

    return NoteContent(
        repo=repo,
        slug=slug,
        meta=meta,
        html=rendered_html,
        source_path=path,
        toc_tokens=toc_html,
    )


def check_note_permission(user, note_content: NoteContent | None) -> bool:
    """兼容旧调用，转发到 notes.permissions。"""

    from .permissions import can_access_note_content

    return can_access_note_content(user, note_content)


__all__ = [
    "InvalidNotePathError",
    "NoteNotFoundError",
    "NoteContent",
    "ReadmeNavigation",
    "normalize_repo_name",
    "resolve_note_markdown_path",
    "render_note_markdown",
    "rewrite_relative_urls",
    "limit_navigation_depth",
    "get_readme_navigation",
    "check_note_permission",
]
