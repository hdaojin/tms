from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from core.utils.markdown import render_markdown_text
from core.documents.markdown import (
    MarkdownDetailsError as NoteDetailsParseError,
    MarkdownRenderError as NoteMarkdownRenderError,
    render_content_markdown,
)

from .html import NOTE_HTML_CLEANER
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


_NOTE_RENDER_ERROR = "无法显示笔记正文，请联系管理员。"


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


def _rewrite_url(url: str | None, repo: str, repo_root: Path, current_dir: str) -> str | None:
    if not url:
        return url
    url = url.strip()
    if url.startswith("//") or "\\" in url or any(ord(char) < 32 for char in url):
        return None
    if url.startswith(("#", "?", "/")):
        return url

    try:
        split = urlsplit(url)
    except ValueError:
        return None
    if split.scheme:
        if split.scheme in {"http", "https", "ftp"}:
            return url if split.hostname else None
        return url if split.scheme in {"mailto", "tel"} and not split.netloc else None
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

    soup = BeautifulSoup(html, "lxml")
    root = soup.body or soup
    for tag in list(root.find_all(href=True)):
        if tag.decomposed:
            continue
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


def build_note_outline(rendered_html: str, min_level: int = 2, max_level: int = 4) -> str:
    """从正文的 H2-H4 标题生成最多三级的层级大纲。"""

    if not rendered_html or min_level > max_level:
        return ""
    try:
        from bs4 import BeautifulSoup
    except Exception:  # pragma: no cover
        return ""

    soup = BeautifulSoup(rendered_html, "lxml")
    root = soup.body or soup
    heading_names = [f"h{level}" for level in range(min_level, max_level + 1)]
    outline: list[dict[str, Any]] = []
    ancestors: list[tuple[int, dict[str, Any]]] = []

    for heading in root.find_all(heading_names):
        anchor_id = heading.get("id")
        title = heading.get_text(" ", strip=True)
        if not isinstance(anchor_id, str) or not anchor_id or not title:
            continue

        level = int(heading.name[1:])
        node: dict[str, Any] = {
            "anchor_id": anchor_id,
            "title": title,
            "children": [],
        }
        while ancestors and ancestors[-1][0] >= level:
            ancestors.pop()
        if ancestors:
            ancestors[-1][1]["children"].append(node)
        else:
            outline.append(node)
        ancestors.append((level, node))

    def render_items(items: list[dict[str, Any]]) -> str:
        if not items:
            return ""
        parts = ["<ul>"]
        for item in items:
            anchor_id = html.escape(item["anchor_id"], quote=True)
            title = html.escape(item["title"])
            parts.append(f'<li><a href="#{anchor_id}">{title}</a>')
            parts.append(render_items(item["children"]))
            parts.append("</li>")
        parts.append("</ul>")
        return "".join(parts)

    return render_items(outline)


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

    rewritten_soup = BeautifulSoup(rewritten, "lxml")
    rewritten_root = rewritten_soup.body or rewritten_soup
    note_prefix = f"/notes/{repo}/"
    asset_prefix = f"/notes-files/{repo}/"
    for anchor in list(rewritten_root.find_all("a", href=True)):
        if anchor.decomposed:
            continue
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
    navigation_html = NOTE_HTML_CLEANER.clean(limit_navigation_depth(rewritten, max_depth=max_depth))

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
    """读取 Markdown，生成正文和 H2-H4 三级标题大纲。"""

    try:
        current_dir = path.parent.relative_to(repo_root).as_posix()
    except ValueError:
        raise InvalidNotePathError("Note path escaped repository root") from None

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        rendered_html = ""
        meta = {"_parse_error": True, "_parse_error_message": "无法读取笔记，请联系管理员。"}
        toc_html = ""
    else:
        try:
            rendered = render_content_markdown(
                content,
                metadata=True,
                html_postprocessor=lambda value: rewrite_relative_urls(
                    value, repo, repo_root, current_dir=current_dir,
                ),
            )
        except NoteDetailsParseError as exc:
            rendered_html = _render_details_parse_error(content, exc)
            meta = {"_parse_error": True, "_parse_error_message": str(exc)}
            toc_html = ""
        except NoteMarkdownRenderError:
            rendered_html = f'<p role="alert">{_NOTE_RENDER_ERROR}</p>'
            meta = {}
            toc_html = ""
        else:
            rendered_html = f'<p role="alert">{_NOTE_RENDER_ERROR}</p>' if rendered.failed else rendered.html
            meta = rendered.meta
            toc_html = build_note_outline(rendered_html)

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
    "build_note_outline",
    "get_readme_navigation",
    "check_note_permission",
]
