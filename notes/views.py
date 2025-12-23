"""Views for notes app."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.cache import cache

from django.conf import settings
from django.db.models import Prefetch

from core.utils.markdown import render_markdown_text

from .models import NoteRepo
from .utils import (
	InvalidNotePathError,
	NoteNotFoundError,
	check_note_permission,
	normalize_repo_name,
	render_note_markdown,
	resolve_note_markdown_path,
	rewrite_relative_urls,
	get_nav_order_from_readme,
)

logger = logging.getLogger(__name__)


@login_required
def notes_repo_list_view(request: HttpRequest) -> HttpResponse:
	"""List top-level note repositories under NOTES_ROOT."""

	notes_root = Path(settings.NOTES_ROOT)
	repo_dirs: set[str] = set()
	if notes_root.exists():
		for child in notes_root.iterdir():
			if child.is_dir():
				repo_dirs.add(child.name)

	# Fetch NoteRepo entries for existing directories.
	note_repos_all = (
		NoteRepo.objects.filter(slug__in=repo_dirs)
		.prefetch_related(Prefetch("allowed_groups"))
		.order_by("order", "slug")
	)

	user_group_ids = set(request.user.groups.values_list("id", flat=True))
	is_superuser = request.user.is_superuser
	visible_repos: list[NoteRepo] = []
	invisible_repos: list[NoteRepo] = []
	for repo in note_repos_all:
		allowed_groups = list(repo.allowed_groups.all())
		allowed_group_ids = {g.id for g in allowed_groups}
		has_group_access = is_superuser or not allowed_groups or bool(user_group_ids.intersection(allowed_group_ids))
		if not has_group_access or not repo.is_visible:
			invisible_repos.append(repo)
			continue
		visible_repos.append(repo)

	context: dict[str, Any] = {
		"title": "黄老师的笔记列表",
		"title_icon": "icon-[tabler--book]",
		"repos": visible_repos,
		"invisible_repos": [],
		"unregistered_repos": [],
		"missing_repos": [],
		"repo_stats_rows": [],
	}

	if is_superuser:
		registered_slugs = {repo.slug for repo in note_repos_all}
		unregistered_repos = sorted(repo_dirs - registered_slugs)
		missing_repos = list(
			NoteRepo.objects.exclude(slug__in=repo_dirs)
			.prefetch_related(Prefetch("allowed_groups"))
			.order_by("order", "slug")
		)
		repo_stats_rows = [
			{
				"label": "总目录数",
				"count": len(repo_dirs),
				"names": sorted(repo_dirs),
			},
			{
				"label": "已显示的笔记库",
				"count": len(visible_repos),
				"names": [repo.slug for repo in visible_repos],
			},
			{
				"label": "设置为不可见的笔记库",
				"count": len(invisible_repos),
				"names": [repo.slug for repo in invisible_repos],
			},
			{
				"label": "未在后台注册的笔记库",
				"count": len(unregistered_repos),
				"names": unregistered_repos,
			},
			{
				"label": "已注册但目录缺失的笔记库",
				"count": len(missing_repos),
				"names": [repo.slug for repo in missing_repos],
			},
		]
		context.update(
			{
				"total_repo_dirs": len(repo_dirs),
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
def note_detail_view(
	request: HttpRequest, repo: str, slug: str | None = None, *args: Any, **kwargs: Any
) -> HttpResponse:
	"""Render a single note by repo/slug."""

	def _normalize_slug_for_nav(slug_value: str | None) -> str:
		if not slug_value:
			return ""
		cleaned = slug_value.strip("/")
		if cleaned.lower().endswith(".md"):
			cleaned = cleaned[:-3]
		if cleaned.lower() == "readme":
			return ""
		return cleaned

	def _build_note_url(slug_value: str) -> str:
		slug_clean = slug_value.strip("/")
		return f"/notes/{safe_repo}/" if not slug_clean else f"/notes/{safe_repo}/{slug_clean}/"

	def _read_readme_nav(base_dir: Path) -> str:
		readme_path = base_dir / "README.md"
		if not readme_path.exists():
			return ""
		lines = readme_path.read_text(encoding="utf-8").splitlines()
		start_idx = end_idx = None
		for idx, line in enumerate(lines):
			if "<!-- TOC_START -->" in line:
				start_idx = idx + 1
			if "<!-- TOC_END -->" in line:
				end_idx = idx
				break
		if start_idx is None or end_idx is None or start_idx >= end_idx:
			return ""
		segment = "\n".join(lines[start_idx:end_idx])
		if not segment.strip():
			return ""
		# Exclude `metadata` to avoid treating arbitrary leading `Key: Value` as metadata here.
		html = render_markdown_text(
			segment,
			extensions=("fenced-code-blocks", "tables", "toc", "header-ids", "break-on-newline", "smarty-pants"),
			lower_meta_keys=False,
		).html
		html = rewrite_relative_urls(html, repo, current_dir="")
		return html

	try:
		safe_repo = normalize_repo_name(repo)
		path = resolve_note_markdown_path(safe_repo, slug)
		slug_key = _normalize_slug_for_nav(slug) or "README"
		cache_key = f"notes:{safe_repo}:{slug_key}"
		cached = cache.get(cache_key)
		if cached:
			note = cached
		else:
			note = render_note_markdown(path, safe_repo, slug_key)
			cache.set(cache_key, note, timeout=getattr(settings, "CACHE_TIMEOUT", None))
	except InvalidNotePathError as exc:
		logger.warning("Invalid note path: repo=%s slug=%s error=%s", repo, slug, exc)
		raise Http404("Invalid note path") from exc
	except NoteNotFoundError as exc:
		logger.warning("Note not found: repo=%s slug=%s", repo, slug)
		raise Http404("Note not found") from exc

	if not check_note_permission(request.user, note):
		logger.warning("Permission denied for user=%s repo=%s slug=%s", request.user, repo, slug)
		return HttpResponseForbidden()

	parse_error = bool(note.meta.get("_parse_error")) if isinstance(note.meta, dict) else False

	base_dir = Path(settings.NOTES_ROOT) / safe_repo
	nav_items = get_nav_order_from_readme(base_dir)

	# Ensure README is always the first item, and avoid duplicates if it's also in TOC
	full_nav_items = [{"slug": "", "title": "README"}] + [item for item in nav_items if item["slug"] != ""]

	current_slug = _normalize_slug_for_nav(slug)
	prev_note = next_note = None
	current_note_title = slug if slug else "README"

	current_idx = -1
	for idx, item in enumerate(full_nav_items):
		if item["slug"] == current_slug:
			current_idx = idx
			current_note_title = item["title"]
			break

	if current_idx != -1:
		if current_idx > 0:
			prev_item = full_nav_items[current_idx - 1]
			prev_note = {"title": prev_item["title"], "url": _build_note_url(prev_item["slug"])}
		if current_idx + 1 < len(full_nav_items):
			next_item = full_nav_items[current_idx + 1]
			next_note = {"title": next_item["title"], "url": _build_note_url(next_item["slug"])}

	# markdown2 already provides HTML toc (<ul>...), pass through directly.
	toc_html = note.toc_tokens
	readme_toc_html = _read_readme_nav(base_dir)

	# Get repo title and notes root name for breadcrumbs
	repo_title = repo
	try:
		repo_obj = NoteRepo.objects.filter(slug=safe_repo).first()
		if repo_obj and repo_obj.title:
			repo_title = repo_obj.title
	except Exception:
		pass
	
	notes_root_name = Path(settings.NOTES_ROOT).name

	context = {
		"note": note,
		"meta": note.meta,
		"repo": note.repo,
		"repo_title": repo_title,
		"notes_root_name": notes_root_name,
		"current_note_title": current_note_title,
		"slug": note.slug,
		"meta_parse_error": parse_error,
		"meta_parse_error_message": note.meta.get("_parse_error_message") if isinstance(note.meta, dict) else None,
		"prev_note": prev_note,
		"next_note": next_note,
		"title": note.meta.get("task", note.slug) if isinstance(note.meta, dict) else note.slug,
		"title_icon": "icon-[tabler--book]",	
		"toc_html": toc_html,
		"readme_toc_html": readme_toc_html,
	}
	return render(request, "notes/note_detail.html", context)


@login_required
def note_print_view(request: HttpRequest, repo: str, slug: str) -> HttpResponse:
	"""Render a print-friendly note page."""

	def _as_lines(value: Any) -> dict[str, Any]:
		if not value:
			return {
				"is_list": False,
				"item": "",
			}
		if isinstance(value, (list, tuple)):
			return {
					"is_list": True,
					"items": [str(v) for v in value if v is not None and str(v).strip()]
			}
		else:
			return {
				"is_list": False,
				"item": str(value).strip(),
			}

	try:
		safe_repo = normalize_repo_name(repo)
		path = resolve_note_markdown_path(safe_repo, slug)
		note = render_note_markdown(path, safe_repo, slug)
	except InvalidNotePathError as exc:
		logger.warning("Invalid note path: repo=%s slug=%s error=%s", repo, slug, exc)
		raise Http404("Invalid note path") from exc
	except NoteNotFoundError as exc:
		logger.warning("Note not found: repo=%s slug=%s", repo, slug)
		raise Http404("Note not found") from exc

	if not check_note_permission(request.user, note):
		logger.warning("Permission denied for user=%s repo=%s slug=%s", request.user, repo, slug)
		return HttpResponseForbidden()

	meta = note.meta if isinstance(note.meta, dict) else {}

	print_meta = {
		"class": meta.get("class"),
		"document": meta.get("document"),
		"role": meta.get("role"),
		"updated_at": meta.get("updated_at"),
		"author": meta.get("author"),
		"module": meta.get("module"),
		"task": meta.get("task"),
		"objectives": _as_lines(meta.get("objectives")),
		"contents": _as_lines(meta.get("contents")),
		"summary": {
			"objective_achievement": _as_lines(meta.get("summary", {}).get("objective_achievement")),
			"shortcomings": _as_lines(meta.get("summary", {}).get("shortcomings")),
			"improvement_plan": _as_lines(meta.get("summary", {}).get("improvement_plan")),
		},
	}

	context = {
		"note": note,
		"meta": meta,
		"print_meta": print_meta,
		"html": note.html,
		"repo": note.repo,
		"slug": note.slug,
		"title": meta.get("task", note.slug),
		"title_icon": "icon-[tabler--printer]",
	}
	return render(request, "notes/print_note.html", context)


@login_required
def note_asset_view(request: HttpRequest, repo: str, asset_path: str) -> HttpResponse:
	"""Serve note assets (images/attachments) from NOTES_ROOT with safety checks."""

	try:
		safe_repo = normalize_repo_name(repo)
	except InvalidNotePathError as exc:
		logger.warning("Invalid asset repo: %s", repo)
		raise Http404("Invalid repo") from exc

	base = Path(settings.NOTES_ROOT) / safe_repo
	candidate = base / asset_path

	try:
		resolved = candidate.resolve(strict=True)
	except FileNotFoundError as exc:  # noqa: BLE001
		logger.info("Asset not found: repo=%s path=%s", repo, asset_path)
		raise Http404("File not found") from exc

	if not resolved.is_relative_to(base.resolve()):
		logger.warning("Path traversal blocked for asset: repo=%s path=%s", repo, asset_path)
		raise Http404("Invalid path")

	if not resolved.is_file():
		logger.info("Asset not a file: repo=%s path=%s", repo, asset_path)
		raise Http404("File not found")

	if not check_note_permission(request.user, None):  # TODO: enforce fine-grained permission
		logger.info("Permission denied for asset: user=%s repo=%s path=%s", request.user, repo, asset_path)
		return HttpResponseForbidden()

	mime_type, _ = mimetypes.guess_type(str(resolved))
	return FileResponse(open(resolved, "rb"), content_type=mime_type or "application/octet-stream") # type: ignore
