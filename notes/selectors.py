from pathlib import Path
from typing import Iterable

from django.conf import settings

from .models import NoteRepo
from .paths import InvalidNotePathError, NoteNotFoundError, normalize_note_relative_path, resolve_note_repo_root


def note_repo_directory_exists(relative_path: str) -> bool:
    try:
        resolve_note_repo_root(relative_path)
    except (InvalidNotePathError, NoteNotFoundError, OSError, RuntimeError):
        return False
    return True


def note_repo_directory_stats(repos: Iterable[NoteRepo]) -> list[tuple[str, list[str]]]:
    notes_root = Path(settings.NOTES_ROOT)
    top_level_dirs = {child.name for child in notes_root.iterdir() if child.is_dir()} if notes_root.is_dir() else set()
    covered_dirs: set[str] = set()
    visible, hidden, missing = [], [], []

    for repo in repos:
        name = f"{repo.slug} → {repo.relative_path}"
        try:
            path = normalize_note_relative_path(repo.relative_path)
        except InvalidNotePathError:
            missing.append(name)
            continue
        covered_dirs.add(path.split("/", 1)[0])
        if not note_repo_directory_exists(path):
            missing.append(name)
        elif repo.is_visible:
            visible.append(name)
        else:
            hidden.append(name)

    return [
        ("全部顶层目录", sorted(top_level_dirs)),
        ("已显示的笔记仓库", visible),
        ("已隐藏的笔记仓库", hidden),
        ("未登记的顶层目录", sorted(top_level_dirs - covered_dirs)),
        ("目录缺失或不可用", missing),
    ]
