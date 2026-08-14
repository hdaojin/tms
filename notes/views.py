"""Views for notes app."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.urls import reverse

from .models import NoteRepo
from .paths import (
    InvalidNotePathError,
    NoteNotFoundError,
    normalize_note_relative_path,
    resolve_note_repo_root,
    resolve_repo_relative_path,
)
from .permissions import can_access_note_repo
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

    notes_root = Path(settings.NOTES_ROOT)
    top_level_dirs = {
        child.name for child in notes_root.iterdir() if child.is_dir()
    } if notes_root.exists() else set()
    note_repos_all = list(
        NoteRepo.objects.prefetch_related(Prefetch("allowed_groups")).order_by("order", "slug")
    )

    existing_repos: list[NoteRepo] = []
    missing_repos: list[NoteRepo] = []
    covered_top_level_dirs: set[str] = set()
    for repo in note_repos_all:
        try:
            normalized = normalize_note_relative_path(repo.relative_path)
            covered_top_level_dirs.add(PurePosixPath(normalized).parts[0])
            resolve_note_repo_root(normalized)
        except (InvalidNotePathError, NoteNotFoundError, OSError):
            missing_repos.append(repo)
            continue
        existing_repos.append(repo)

    visible_repos: list[NoteRepo] = []
    invisible_repos: list[NoteRepo] = []
    for repo in existing_repos:
        if repo.is_visible and can_access_note_repo(request.user, repo.slug, note_repo=repo):
            visible_repos.append(repo)
        else:
            invisible_repos.append(repo)

    context: dict[str, Any] = {
        "title": "黄老师的笔记列表",
        "title_icon": "icon-[tabler--book]",
        "repos": visible_repos,
        "invisible_repos": [],
        "unregistered_repos": [],
        "missing_repos": [],
        "repo_stats_rows": [],
    }
    if request.user.is_superuser:
        unregistered_repos = sorted(top_level_dirs - covered_top_level_dirs)
        display_name = lambda repo: f"{repo.slug} → {repo.relative_path}"  # noqa: E731
        repo_stats_rows = [
            {"label": "顶层目录数", "count": len(top_level_dirs), "names": sorted(top_level_dirs)},
            {
                "label": "已显示的笔记库",
                "count": len(visible_repos),
                "names": [display_name(repo) for repo in visible_repos],
            },
            {
                "label": "设置为不可见或无权访问的笔记库",
                "count": len(invisible_repos),
                "names": [display_name(repo) for repo in invisible_repos],
            },
            {
                "label": "未在后台注册的顶层目录",
                "count": len(unregistered_repos),
                "names": unregistered_repos,
            },
            {
                "label": "已注册但目录缺失的笔记库",
                "count": len(missing_repos),
                "names": [display_name(repo) for repo in missing_repos],
            },
        ]
        context.update(
            {
                "total_repo_dirs": len(top_level_dirs),
                "visible_repo_count": len(visible_repos),
                "invisible_repos": invisible_repos,
                "invisible_repo_count": len(invisible_repos),
                "unregistered_repos": unregistered_repos,
                "unregistered_repo_count": len(unregistered_repos),
                "missing_repos": missing_repos,
                "missing_repo_count": len(missing_repos),
                "repo_stats_rows": repo_stats_rows,
            }
        )
    return render(request, "notes/repo_list.html", context)


@login_required
@permission_required("notes.view_noterepo", raise_exception=True)
def note_detail_view(
    request: HttpRequest, repo: str, slug: str | None = None, *args: Any, **kwargs: Any
) -> HttpResponse:
    """渲染已登记笔记仓库内的单篇 Markdown。"""

    safe_repo, repo_obj = _get_registered_repo(repo)
    if not can_access_note_repo(request.user, safe_repo, note_repo=repo_obj):
        logger.warning("Permission denied for user=%s repo=%s slug=%s", request.user, repo, slug)
        return HttpResponseForbidden()

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
        "slug": current_slug,
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
    return render(request, "notes/note_detail.html", context)


@login_required
@permission_required("notes.view_noterepo", raise_exception=True)
def note_print_view(request: HttpRequest, repo: str, slug: str) -> HttpResponse:
    """渲染适合打印的训练日志页面。"""

    def as_lines(value: Any) -> dict[str, Any]:
        if not value:
            return {"is_list": False, "item": ""}
        if isinstance(value, (list, tuple)):
            return {
                "is_list": True,
                "items": [str(item) for item in value if item is not None and str(item).strip()],
            }
        return {"is_list": False, "item": str(value).strip()}

    safe_repo, repo_obj = _get_registered_repo(repo)
    if not can_access_note_repo(request.user, safe_repo, note_repo=repo_obj):
        return HttpResponseForbidden()
    try:
        repo_root = resolve_note_repo_root(repo_obj.relative_path)
        path = resolve_note_markdown_path(repo_root, slug)
        note = render_note_markdown(path, safe_repo, repo_root, _normalize_slug_for_nav(slug))
    except (InvalidNotePathError, NoteNotFoundError) as exc:
        raise Http404("Note not found") from exc

    meta = note.meta if isinstance(note.meta, dict) else {}
    summary = meta.get("summary") if isinstance(meta.get("summary"), dict) else {}
    print_meta = {
        "class": meta.get("class"),
        "document": meta.get("document"),
        "role": meta.get("role"),
        "updated_at": meta.get("updated_at"),
        "author": meta.get("author"),
        "module": meta.get("module"),
        "task": meta.get("task"),
        "objectives": as_lines(meta.get("objectives")),
        "contents": as_lines(meta.get("contents")),
        "summary": {
            "objective_achievement": as_lines(summary.get("objective_achievement")),
            "shortcomings": as_lines(summary.get("shortcomings")),
            "improvement_plan": as_lines(summary.get("improvement_plan")),
        },
    }
    context = {
        "note": note,
        "meta": meta,
        "print_meta": print_meta,
        "html": note.html,
        "repo": safe_repo,
        "slug": note.slug,
        "title": meta.get("task", note.slug),
        "title_icon": "icon-[tabler--printer]",
    }
    return render(request, "notes/print_note.html", context)


@login_required
@permission_required("notes.view_noterepo", raise_exception=True)
def note_asset_view(request: HttpRequest, repo: str, asset_path: str) -> HttpResponse:
    """在已登记仓库根目录内安全提供图片和附件。"""

    safe_repo, repo_obj = _get_registered_repo(repo)
    if not can_access_note_repo(request.user, safe_repo, note_repo=repo_obj):
        return HttpResponseForbidden()
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

    mime_type, _ = mimetypes.guess_type(str(resolved))
    return FileResponse(open(resolved, "rb"), content_type=mime_type or "application/octet-stream")  # noqa: SIM115
