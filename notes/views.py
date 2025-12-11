"""Views for notes app."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.core.cache import cache

from django.conf import settings
from django.db.models import Prefetch

from .models import NoteRepo
from .utils import (
	InvalidNotePathError,
	NoteNotFoundError,
	check_note_permission,
	normalize_repo_name,
	render_note_markdown,
	resolve_note_markdown_path,
)

logger = logging.getLogger(__name__)


class NotesRepoListView(LoginRequiredMixin, TemplateView):
	"""List top-level note repositories under NOTES_ROOT."""

	template_name = "notes/repo_list.html"
	extra_context = {
        "title": "黄老师的笔记列表",
        "title_icon" : "icon-[tabler--book]"
    }
    
	def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
		ctx = super().get_context_data(**kwargs)
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

		user_group_ids = set(self.request.user.groups.values_list("id", flat=True))
		is_superuser = self.request.user.is_superuser
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

		ctx["repos"] = visible_repos

		if is_superuser:
			registered_slugs = {repo.slug for repo in note_repos_all}
			unregistered_repos = sorted(repo_dirs - registered_slugs)
			missing_repos = list(
				NoteRepo.objects.exclude(slug__in=repo_dirs)
				.prefetch_related(Prefetch("allowed_groups"))
				.order_by("order", "slug")
			)
			ctx.update(
				{
					"total_repo_dirs": len(repo_dirs),
					"visible_repo_count": len(visible_repos),
					"invisible_repos": invisible_repos,
					"invisible_repo_count": len(invisible_repos),
					"unregistered_repos": unregistered_repos,
					"unregistered_repo_count": len(unregistered_repos),
					"missing_repos": missing_repos,
					"missing_repo_count": len(missing_repos),
				}
			)

		return ctx


class NoteDetailView(LoginRequiredMixin, View):
	"""Render a single note by repo/slug."""

	template_name = "notes/note_detail.html"

	def get(self, request: HttpRequest, repo: str, slug: str | None = None, *args: Any, **kwargs: Any) -> HttpResponse:
		try:
			safe_repo = normalize_repo_name(repo)
			path = resolve_note_markdown_path(safe_repo, slug)
			slug_key = slug or "README"
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
		context = {
			"note": note,
			"meta": note.meta,
			"repo": note.repo,
			"slug": note.slug,
			"meta_parse_error": parse_error,
			"meta_parse_error_message": note.meta.get("_parse_error_message") if isinstance(note.meta, dict) else None,
		}
		return self.render_to_response(context)

	def render_to_response(self, context: dict[str, Any]) -> HttpResponse:
		from django.shortcuts import render

		return render(self.request, self.template_name, context)


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
	return FileResponse(open(resolved, "rb"), content_type=mime_type or "application/octet-stream")
