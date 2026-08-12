from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from core.utils.markdown import render_markdown_text

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
        rendered = render_markdown_text(
            content,
            html_postprocessor=lambda html: rewrite_relative_urls(
                html,
                repo,
                repo_root,
                current_dir=current_dir,
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
