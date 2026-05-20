from __future__ import annotations

import re
from dataclasses import dataclass
import posixpath
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from core.utils.markdown import render_markdown_text
from core.constants import NOTES_ROOT


class InvalidNotePathError(Exception):
    """当请求的笔记路径非法（含穿越）或逃逸出 NOTES_ROOT 时抛出。"""


class NoteNotFoundError(Exception):
    """当笔记文件不存在时抛出。"""


@dataclass
class NoteContent:
    """渲染后的笔记内容与元数据容器。"""

    repo: str
    slug: str
    meta: dict[str, Any]
    html: str
    source_path: Path
    toc_tokens: str | None


def normalize_repo_name(repo: str) -> str:
    """校验 repo 名称，只允许 `[A-Za-z0-9_-]`，否则抛出异常。"""

    if not repo or not re.fullmatch(r"[A-Za-z0-9_-]+", repo):
        raise InvalidNotePathError("Invalid repo name")
    return repo


def _safe_join(base: Path, *parts: str) -> Path:
    """在 base 下拼接路径，并确保最终结果仍位于 NOTES_ROOT 内。

    说明：
    - 这里的校验是为了防止通过 `..` 或软链接等方式进行路径穿越。
    - 返回值保持为“候选路径”（可能尚不存在），方便调用方继续 exists() 判断。
    """

    candidate = base.joinpath(*parts)
    notes_root = Path(NOTES_ROOT).resolve()
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(notes_root):
        raise InvalidNotePathError("Path traversal detected")
    return candidate


def resolve_note_markdown_path(repo: str, slug: str | None) -> Path:
    """把 (repo, slug) 解析成 NOTES_ROOT 下的 markdown 文件路径。

    路由约定：
    - slug 为空：优先 `README.md`
    - slug 为 `a/b`：优先 `a/b.md`，其次 `a/b/README.md`
    - slug 允许带 `.md` 后缀（会自动去掉）
    """

    safe_repo = normalize_repo_name(repo)
    base = Path(NOTES_ROOT) / safe_repo

    def _readme_or_raise() -> Path:
        candidate = _safe_join(base, "README.md")
        if candidate.exists():
            return candidate
        raise NoteNotFoundError("README not found")

    if not slug:
        return _readme_or_raise()

    slug_path = PurePosixPath(slug)
    if slug_path.is_absolute() or ".." in slug_path.parts:
        raise InvalidNotePathError("Invalid slug path")

    normalized_slug = slug_path.as_posix().strip("/")
    if not normalized_slug:
        return _readme_or_raise()

    # 允许传入已带 `.md` 后缀的 slug（例如从 markdown 链接直接来）。
    if normalized_slug.lower().endswith(".md"):
        normalized_slug = normalized_slug[:-3]

    candidates = (
        _safe_join(base, f"{normalized_slug}.md"),
        _safe_join(base, normalized_slug, "README.md"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise NoteNotFoundError("Note file not found")


def rewrite_relative_urls(html: str, repo: str, current_dir: str = "") -> str:
    """把 HTML 中的相对 href/src 改写为站内 URL（使用 bs4 + lxml）。

    说明：
    - 这里优先选择“更好懂/更少代码”，因此使用 BeautifulSoup 做 HTML 解析。
    - 注意：bs4 在输出 HTML 时可能会重排属性顺序、统一引号、补全某些标签（这是正常现象）。
    """

    current_dir_path = PurePosixPath(current_dir or ".")

    def is_external_url(url: str) -> bool:
        lowered = url.lower()
        if lowered.startswith(("http://", "https://", "//", "mailto:", "tel:", "data:", "javascript:")):
            return True
        return False

    def resolve_relative_path(path: str) -> str:
        """把相对 path 解析到 current_dir 下，并防止输出以 `..` 开头的穿越路径。"""

        if not path:
            return ""
        joined = posixpath.join(current_dir_path.as_posix(), path)
        normalized = posixpath.normpath(joined).lstrip("/")
        if normalized in {".", ".."}:
            return ""
        while normalized.startswith("../"):
            normalized = normalized[3:]
        return normalized

    def rewrite_url(url: str | None) -> str | None:
        if not url:
            return url
        if url.startswith(("#", "?")):
            return url
        if url.startswith("/") or is_external_url(url):
            return url

        split = urlsplit(url)
        if split.scheme or split.netloc:
            return url
        if not split.path and (split.query or split.fragment):
            return url

        resolved_path = resolve_relative_path(split.path or "")
        suffix = PurePosixPath(resolved_path).suffix.lower()
        first_segment = resolved_path.split("/", 1)[0] if resolved_path else ""
        is_assets_path = first_segment == "assets"

        # `.md` 或无后缀：当作“笔记页面跳转”（assets 目录例外）
        if suffix in {".md", ""} and not is_assets_path:
            slug_path = resolved_path
            if slug_path.lower().endswith(".md"):
                slug_path = slug_path[:-3]
            slug_path = slug_path.strip("/")
            base = f"/notes/{repo}/"
            target = base if not slug_path else f"/notes/{repo}/{slug_path}/"
        else:
            target = f"/notes-files/{repo}/{resolved_path}"

        return urlunsplit(("", "", target, split.query, split.fragment))

    # 延迟导入：避免在某些环境（例如未安装依赖的脚本工具）中仅 import 本模块就报错。
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    # markdown 渲染的通常是“片段”（没有 <html>/<body>），但 lxml 解析后会自动补齐；
    # 为了保持调用方的预期，这里对片段只返回 body 内部内容。
    html_lower = html.lower()
    is_fragment = "<html" not in html_lower and "<body" not in html_lower
    root = soup.body if (is_fragment and soup.body) else soup

    for tag in root.find_all(href=True):
        href = tag.get("href")
        if isinstance(href, str) or href is None:
            rewritten = rewrite_url(href)
            if rewritten is not None:
                tag["href"] = rewritten
    for tag in root.find_all(src=True):
        src = tag.get("src")
        if isinstance(src, str) or src is None:
            rewritten = rewrite_url(src)
            if rewritten is not None:
                tag["src"] = rewritten

    return root.decode_contents() if root is soup.body else str(root)


def render_note_markdown(path: Path, repo: str, slug: str) -> NoteContent:
    """读取 markdown（可选 front matter），渲染为 HTML，并改写相对链接。"""

    # current_dir 用于把相对链接（例如 `../img.png`）解析为正确的仓库内路径。
    repo_base = Path(NOTES_ROOT) / repo
    try:
        current_dir = path.parent.relative_to(repo_base).as_posix()
    except ValueError:
        current_dir = ""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        rendered_html = ""
        meta = {"_parse_error": True, "_parse_error_message": str(exc)}
        toc_html = None
    else:
        rendered = render_markdown_text(
            content,
            html_postprocessor=lambda html: rewrite_relative_urls(html, repo, current_dir=current_dir),
        )
        rendered_html = rendered.html
        meta = rendered.meta
        toc_html = rendered.toc

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


def get_nav_order_from_readme(repo_path: Path) -> list[dict[str, str]]:
    """从 README.md 的 TOC 区域解析笔记导航顺序。"""
    readme_path = repo_path / "README.md"
    if not readme_path.exists():
        return []

    try:
        content = readme_path.read_text(encoding="utf-8")
    except Exception:
        return []

    lines = content.splitlines()

    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if "<!-- TOC_START -->" in line:
            start_idx = i
        elif "<!-- TOC_END -->" in line:
            end_idx = i
            break

    if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
        return []

    toc_lines = lines[start_idx + 1 : end_idx]
    toc_text = "\n".join(toc_lines)

    # 提取 markdown 链接 [text](url)
    matches = re.findall(r"\[([^\]]*)\]\(([^)]*)\)", toc_text)

    nav_items = []
    for text, link in matches:
        # 去掉可能存在的 title 属性
        url = link.split()[0]

        # 去掉 anchor
        if "#" in url:
            url = url.split("#", 1)[0]

        if not url:
            continue

        if url.lower().startswith(("http:", "https:", "ftp:", "mailto:", "//")):
            continue

        # Normalize
        if url.lower().endswith(".md"):
            url = url[:-3]

        if url.startswith("./"):
            url = url[2:]

        slug = url.strip("/")
        if slug.lower() == "readme":
            slug = ""

        nav_items.append({"slug": slug, "title": text.strip()})

    return nav_items


__all__ = [
    "InvalidNotePathError",
    "NoteNotFoundError",
    "NoteContent",
    "normalize_repo_name",
    "resolve_note_markdown_path",
    "render_note_markdown",
    "rewrite_relative_urls",
    "check_note_permission",
    "get_nav_order_from_readme",
]
