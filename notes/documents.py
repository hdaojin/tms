"""Resolve authorized notebook resources for document rendering."""

from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from django.urls import reverse

from core.documents.images import DocumentImages
from .paths import InvalidNotePathError, resolve_repo_relative_path


def local_image_path(src, repo_slug, root, note_path):
    target = urlsplit(src)
    if target.scheme or target.netloc or not target.path or src.startswith("//"):
        return None
    path = unquote(target.path)
    if "\\" in path or ":" in path or any(ord(char) < 32 for char in path):
        raise ValueError
    if path.startswith("/"):
        prefix = f"/notes-files/{repo_slug}/"
        if not path.startswith(prefix):
            raise ValueError
        current_dir, path = "", path[len(prefix) :]
    else:
        current_dir = note_path.parent.relative_to(root).as_posix()
    relative, candidate = resolve_repo_relative_path(root, current_dir, path)
    if any(part.startswith(".") for part in PurePosixPath(relative).parts):
        raise ValueError
    if candidate != root.joinpath(*PurePosixPath(relative).parts) or not candidate.is_file():
        raise ValueError
    return relative, candidate



class NoteImages(DocumentImages):
    def __init__(self):
        super().__init__(reserved_bytes=1024 * 1024, reserved_pixels=1_000_000)

    def snapshot(self, entry, repo_slug, root, note_path, issues):
        def resolve_image(src):
            try:
                location = local_image_path(src, repo_slug, root, note_path)
            except InvalidNotePathError as exc:
                raise ValueError from exc
            if location is None:
                return None
            relative, path = location
            return path, reverse("note_asset", kwargs={"repo": repo_slug, "asset_path": relative})

        return self.collect(
            [entry[field] for field in ("note_goal", "note_outline", "note_process")],
            resolve_image, issues,
        )
