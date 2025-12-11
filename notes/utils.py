from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, List, Tuple

import frontmatter
import markdown
from django.conf import settings


logger = logging.getLogger(__name__)


class InvalidNotePathError(Exception):
    """Raised when the requested note path is invalid or escapes NOTES_ROOT."""


class NoteNotFoundError(Exception):
    """Raised when the requested note file does not exist."""


@dataclass
class NoteContent:
    """Container for rendered note content and metadata."""

    repo: str
    slug: str
    meta: dict[str, Any]
    html: str
    source_path: Path


def normalize_repo_name(repo: str) -> str:
    """Ensure repo name uses only [a-zA-Z0-9-_]; otherwise raise error."""

    if not repo or not re.fullmatch(r"[A-Za-z0-9_-]+", repo):
        raise InvalidNotePathError("Invalid repo name")
    return repo


def _safe_join(base: Path, *parts: str) -> Path:
    candidate = base.joinpath(*parts)
    root = Path(settings.NOTES_ROOT).resolve()
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise InvalidNotePathError("Path traversal detected")
    return candidate


def resolve_note_markdown_path(repo: str, slug: str | None) -> Path:
    """Resolve a repo/slug to a markdown file within NOTES_ROOT, with escape protection."""

    safe_repo = normalize_repo_name(repo)
    base = Path(settings.NOTES_ROOT) / safe_repo

    if not slug:
        candidate = _safe_join(base, "README.md")
        if candidate.exists():
            return candidate
        raise NoteNotFoundError("README not found")

    slug_path = PurePosixPath(slug)
    if slug_path.is_absolute() or ".." in slug_path.parts:
        raise InvalidNotePathError("Invalid slug path")

    normalized_slug = slug_path.as_posix().strip("/")
    if not normalized_slug:
        candidate = _safe_join(base, "README.md")
        if candidate.exists():
            return candidate
        raise NoteNotFoundError("README not found")

    # Allow incoming slugs that already include a .md suffix.
    if normalized_slug.lower().endswith(".md"):
        normalized_slug = normalized_slug[:-3]

    primary = _safe_join(base, f"{normalized_slug}.md")
    if primary.exists():
        return primary

    fallback = _safe_join(base, normalized_slug, "README.md")
    if fallback.exists():
        return fallback

    raise NoteNotFoundError("Note file not found")


class _RelativeURLRewriter(HTMLParser):
    """HTML parser that rewrites relative href/src to the notes-files endpoint."""

    def __init__(self, repo: str):
        super().__init__(convert_charrefs=True)
        self.repo = repo
        self._buf: List[str] = []

    # Public API
    @property
    def html(self) -> str:
        return "".join(self._buf)

    # Core helpers
    def _rewrite_url(self, url: str | None) -> str | None:
        if not url:
            return url
        lowered = url.lower()
        if lowered.startswith(("http://", "https://", "//", "mailto:", "tel:")):
            return url
        if url.startswith("/"):
            return url
        return f"/notes-files/{self.repo}/{url}"

    def _format_attrs(self, attrs: List[Tuple[str, str | None]]) -> str:
        formatted: List[str] = []
        for key, value in attrs:
            if key in {"href", "src"}:
                value = self._rewrite_url(value)
            if value is None:
                formatted.append(f" {key}")
            else:
                formatted.append(f" {key}=\"{escape(value, quote=True)}\"")
        return "".join(formatted)

    def _emit_start(self, tag: str, attrs: List[Tuple[str, str | None]], self_closing: bool) -> None:
        attr_str = self._format_attrs(attrs)
        closing = " />" if self_closing else ">"
        self._buf.append(f"<{tag}{attr_str}{closing}")

    # HTMLParser hooks
    def handle_starttag(self, tag, attrs):
        self._emit_start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._emit_start(tag, attrs, True)

    def handle_endtag(self, tag):
        self._buf.append(f"</{tag}>")

    def handle_data(self, data):
        self._buf.append(data)

    def handle_entityref(self, name):
        self._buf.append(f"&{name};")

    def handle_charref(self, name):
        self._buf.append(f"&#{name};")

    def handle_comment(self, data):
        self._buf.append(f"<!--{data}-->")


def rewrite_relative_urls(html: str, repo: str) -> str:
    """Rewrite relative href/src URLs to /notes-files/<repo>/... while leaving absolute URLs untouched."""

    parser = _RelativeURLRewriter(repo)
    parser.feed(html)
    parser.close()
    return parser.html


def render_note_markdown(path: Path, repo: str, slug: str) -> NoteContent:
    """Load markdown with front matter, render to HTML, and rewrite relative links."""

    meta: dict[str, Any] = {}
    try:
        post = frontmatter.load(path)
        meta = dict(post.metadata)
        content = post.content
    except Exception as exc:  # noqa: BLE001
        with path.open("r", encoding="utf-8") as f:
            content = f.read()
        meta = {
            "_parse_error": True,
            "_parse_error_message": str(exc),
        }
        logger.warning("Front matter parse failed repo=%s slug=%s path=%s error=%s", repo, slug, path, exc)

    md = markdown.Markdown(extensions=["fenced_code", "tables", "toc", "attr_list"])
    html = md.convert(content)
    html = rewrite_relative_urls(html, repo)

    return NoteContent(
        repo=repo,
        slug=slug,
        meta=meta,
        html=html,
        source_path=path,
    )


__all__ = [
    "InvalidNotePathError",
    "NoteNotFoundError",
    "NoteContent",
    "normalize_repo_name",
    "resolve_note_markdown_path",
    "render_note_markdown",
    "rewrite_relative_urls",
    "check_note_permission",
]


def check_note_permission(user, note_content: NoteContent | None) -> bool:
    """Repo-aware permission check for notes access.

    Rules:
    - If no matching NoteRepo is found: allow authenticated users (log info).
    - If NoteRepo.is_visible is False: deny unless user.is_superuser.
    - If allowed_groups is non-empty: allow only when user is in any allowed group.
    - If allowed_groups is empty: allow authenticated users.

    LoginRequiredMixin/@login_required already ensure authentication before calling.
    """

    from .models import NoteRepo

    if note_content is None:
        return True

    try:
        note_repo = NoteRepo.objects.filter(slug=note_content.repo).prefetch_related("allowed_groups").first()
    except Exception as exc:  # noqa: BLE001
        logger.error("Permission lookup failed for repo=%s error=%s", note_content.repo, exc)
        return False

    if note_repo is None:
        logger.info("NoteRepo not registered, using default allow: repo=%s", note_content.repo)
        return True

    if note_repo.is_visible is False and not getattr(user, "is_superuser", False):
        return False

    allowed = list(note_repo.allowed_groups.all())
    if allowed:
        user_groups = set(user.groups.all())
        return any(g in user_groups for g in allowed)

    return True
