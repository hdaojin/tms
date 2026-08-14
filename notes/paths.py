from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from django.conf import settings


class InvalidNotePathError(Exception):
    """笔记路径非法或逃逸出允许的根目录。"""


class NoteNotFoundError(Exception):
    """笔记仓库、正文或附件不存在。"""


def normalize_note_relative_path(value: str) -> str:
    """把后台输入规范化为 NOTES_ROOT 下的 POSIX 相对路径。"""

    raw = (value or "").strip().replace("\\", "/")
    if not raw:
        raise InvalidNotePathError("相对路径不能为空")
    if raw.startswith("/") or raw.startswith("//") or re.match(r"^[A-Za-z]:", raw):
        raise InvalidNotePathError("相对路径不能是绝对路径、盘符路径或 UNC 路径")

    path = PurePosixPath(raw)
    if any(part == ".." for part in path.parts):
        raise InvalidNotePathError("相对路径不能包含 ..")

    normalized = path.as_posix().strip("/")
    if normalized in {"", ".", ".."}:
        raise InvalidNotePathError("相对路径必须指向 NOTES_ROOT 下的目录")
    return normalized


def resolve_note_repo_root(relative_path: str, *, require_exists: bool = True) -> Path:
    """解析配置目录，并确保真实路径仍位于 NOTES_ROOT 内。"""

    normalized = normalize_note_relative_path(relative_path)
    notes_root = Path(settings.NOTES_ROOT).resolve()
    candidate = notes_root.joinpath(*PurePosixPath(normalized).parts)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(notes_root):
        raise InvalidNotePathError("笔记仓库路径逃逸出 NOTES_ROOT")
    if require_exists and (not resolved.exists() or not resolved.is_dir()):
        raise NoteNotFoundError("笔记仓库目录不存在")
    return resolved


def resolve_repo_relative_path(repo_root: Path, current_dir: str, value: str) -> tuple[str, Path]:
    """把文档内相对路径解析到仓库根内，允许在仓库内部使用 ..。"""

    decoded = unquote(value or "").replace("\\", "/")
    if decoded.startswith("/") or re.match(r"^[A-Za-z]:", decoded):
        raise InvalidNotePathError("文档路径必须是相对路径")

    base_parts = PurePosixPath(current_dir or ".").parts
    raw_parts = PurePosixPath(decoded).parts
    stack: list[str] = []
    for part in (*base_parts, *raw_parts):
        if part in {"", "."}:
            continue
        if part == "..":
            if not stack:
                raise InvalidNotePathError("文档路径逃逸出笔记仓库")
            stack.pop()
            continue
        stack.append(part)

    relative = PurePosixPath(*stack).as_posix() if stack else ""
    resolved_root = repo_root.resolve()
    candidate = resolved_root.joinpath(*stack).resolve(strict=False)
    if not candidate.is_relative_to(resolved_root):
        raise InvalidNotePathError("文档路径逃逸出笔记仓库")
    return relative, candidate


__all__ = [
    "InvalidNotePathError",
    "NoteNotFoundError",
    "normalize_note_relative_path",
    "resolve_note_repo_root",
    "resolve_repo_relative_path",
]
