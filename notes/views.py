"""Views for notes app."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote

from django.conf import settings
from django.contrib.auth.decorators import login_not_required, login_required
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from core.file_preview import build_inline_preview_response
from core.utils.breadcrumbs import breadcrumb_link, build_breadcrumbs

from .models import NoteRepo
from .paths import (
    InvalidNotePathError,
    NoteNotFoundError,
    resolve_note_repo_root,
    resolve_repo_relative_path,
)
from .permissions import NoteRepoReadAccess, can_access_note_repo, get_note_repo_read_access
from .selectors import note_repo_directory_exists
from .utils import (
    get_readme_navigation,
    normalize_repo_name,
    render_note_markdown,
    resolve_note_markdown_path,
)

logger = logging.getLogger(__name__)


def _get_registered_repo(repo: str) -> tuple[str, NoteRepo]:
    try:
        safe_repo = normalize_repo_name(repo)
    except InvalidNotePathError as exc:
        raise Http404("Invalid repo") from exc
    note_repo = NoteRepo.objects.filter(slug=safe_repo).prefetch_related("allowed_groups").first()
    if note_repo is None:
        raise Http404("Note repository not registered")
    return safe_repo, note_repo


def _note_read_response(response: HttpResponse) -> HttpResponse:
    response.headers.setdefault("Cache-Control", "private, no-store")
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _check_note_read_access(request: HttpRequest, note_repo: NoteRepo) -> HttpResponse | None:
    access = get_note_repo_read_access(request.user, note_repo)
    if access is NoteRepoReadAccess.ALLOWED:
        return None
    if access is NoteRepoReadAccess.LOGIN_REQUIRED:
        return _note_read_response(redirect_to_login(request.get_full_path()))
    if access is NoteRepoReadAccess.PUBLIC_ACCESS_BLOCKED:
        return _note_read_response(HttpResponseNotFound("未找到笔记仓库。"))
    return _note_read_response(HttpResponseForbidden())


def _normalize_slug_for_nav(slug: str | None) -> str:
    if not slug:
        return ""
    cleaned = unquote(slug).replace("\\", "/").strip("/")
    if cleaned.lower().endswith(".md"):
        cleaned = cleaned[:-3]
    return "" if cleaned.lower() == "readme" else cleaned


def _build_note_url(repo: str, slug: str) -> str:
    if not slug:
        return reverse("notes:note_repo_index", kwargs={"repo": repo})
    return reverse("notes:note_detail", kwargs={"repo": repo, "slug": slug})


def _cache_key(repo: NoteRepo, slug: str, path: Path) -> str:
    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        modified_ns = 0
    signature = f"{repo.updated_at.isoformat()}:{repo.relative_path}:{modified_ns}"
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:20]
    return f"notes:{repo.slug}:{slug}:{digest}"


@login_required
@permission_required("notes.view_noterepo", raise_exception=True)
def notes_repo_list_view(request: HttpRequest) -> HttpResponse:
    """列出已登记且目录存在的笔记仓库。"""

    repos = NoteRepo.objects.filter(is_visible=True).prefetch_related("allowed_groups")
    visible_repos = [
        repo
        for repo in repos
        if can_access_note_repo(request.user, repo.slug, note_repo=repo)
        and note_repo_directory_exists(repo.relative_path)
    ]

    context: dict[str, Any] = {
        "title": "黄老师的笔记列表",
        "title_icon": "icon-[tabler--book]",
        "repos": visible_repos,
    }
    context["breadcrumbs"] = build_breadcrumbs(request, context["title"])
    return render(request, "notes/repo_list.html", context)


@login_not_required
@never_cache
def note_detail_view(
    request: HttpRequest, repo: str, slug: str | None = None, *args: Any, **kwargs: Any
) -> HttpResponse:
    """渲染已登记笔记仓库内的单篇 Markdown。"""

    safe_repo, repo_obj = _get_registered_repo(repo)
    if denial := _check_note_read_access(request, repo_obj):
        return denial

    try:
        repo_root = resolve_note_repo_root(repo_obj.relative_path)
        path = resolve_note_markdown_path(repo_root, slug)
        current_slug = _normalize_slug_for_nav(slug)
        slug_key = current_slug or "README"
        cache_key = _cache_key(repo_obj, slug_key, path)
        note = cache.get(cache_key)
        if note is None:
            note = render_note_markdown(path, safe_repo, repo_root, slug_key)
            cache.set(cache_key, note, timeout=getattr(settings, "CACHE_TIMEOUT", None))
    except InvalidNotePathError as exc:
        logger.warning("Invalid note path: repo=%s slug=%s error=%s", repo, slug, exc)
        raise Http404("Invalid note path") from exc
    except NoteNotFoundError as exc:
        logger.warning("Note not found: repo=%s slug=%s", repo, slug)
        raise Http404("Note not found") from exc

    readme_navigation = get_readme_navigation(repo_root, safe_repo)
    full_nav_items = [{"slug": "", "title": "README"}] + [
        item for item in readme_navigation.items if item["slug"]
    ]
    prev_note = next_note = None
    current_note_title = slug_key
    for index, item in enumerate(full_nav_items):
        if item["slug"] != current_slug:
            continue
        current_note_title = item["title"]
        if index > 0:
            previous = full_nav_items[index - 1]
            prev_note = {
                "title": previous["title"],
                "url": _build_note_url(safe_repo, previous["slug"]),
            }
        if index + 1 < len(full_nav_items):
            following = full_nav_items[index + 1]
            next_note = {
                "title": following["title"],
                "url": _build_note_url(safe_repo, following["slug"]),
            }
        break

    meta = note.meta if isinstance(note.meta, dict) else {}
    context = {
        "note": note,
        "meta": meta,
        "repo": safe_repo,
        "repo_title": repo_obj.title or safe_repo,
        "notes_root_name": Path(settings.NOTES_ROOT).name,
        "current_note_title": current_note_title,
        "meta_parse_error": bool(meta.get("_parse_error")),
        "meta_parse_error_message": meta.get("_parse_error_message"),
        "prev_note": prev_note,
        "next_note": next_note,
        "title": meta.get("task", current_note_title),
        "title_icon": "icon-[tabler--book]",
        "toc_html": note.toc_tokens,
        "readme_toc_html": readme_navigation.html,
        "show_right_sidebar": True,
        "wide_sidebars": True,
    }
    parents = [breadcrumb_link("笔记仓库", "notes:repo_list")] if request.user.is_authenticated else []
    parents.append(
        breadcrumb_link(repo_obj.title or safe_repo, "notes:note_repo_index", kwargs={"repo": safe_repo}),
    )
    context["breadcrumbs"] = build_breadcrumbs(request, context["title"], parents)
    return _note_read_response(render(request, "notes/note_detail.html", context))


@login_not_required
def note_asset_view(request: HttpRequest, repo: str, asset_path: str) -> HttpResponse:
    """在已登记仓库根目录内安全提供图片和附件。"""

    _, repo_obj = _get_registered_repo(repo)
    if denial := _check_note_read_access(request, repo_obj):
        return denial
    try:
        repo_root = resolve_note_repo_root(repo_obj.relative_path)
        decoded_path = unquote(asset_path).replace("\\", "/")
        relative_path = PurePosixPath(decoded_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise InvalidNotePathError("Invalid asset path")
        _, resolved = resolve_repo_relative_path(repo_root, "", relative_path.as_posix())
        resolved = resolved.resolve(strict=True)
    except (InvalidNotePathError, NoteNotFoundError, FileNotFoundError) as exc:
        raise Http404("File not found") from exc
    if not resolved.is_relative_to(repo_root.resolve()) or not resolved.is_file():
        raise Http404("File not found")

    return _note_read_response(build_inline_preview_response(resolved, resolved.name, download_unsupported=True))
