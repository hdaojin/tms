from __future__ import annotations

from typing import TYPE_CHECKING

from .models import NoteRepo

if TYPE_CHECKING:
    from .utils import NoteContent


def can_access_note_repo(user, repo_slug: str, *, note_repo: NoteRepo | None = None) -> bool:
    """按已登记的 NoteRepo 配置判断当前用户是否可访问。"""

    if not getattr(user, "is_authenticated", False):
        return False
    if note_repo is None:
        try:
            note_repo = NoteRepo.objects.filter(slug=repo_slug).prefetch_related("allowed_groups").first()
        except Exception:  # noqa: BLE001
            return False
    if note_repo is None:
        return False
    if note_repo.is_visible is False and not getattr(user, "is_superuser", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    allowed = list(note_repo.allowed_groups.all())
    if allowed:
        user_groups = set(user.groups.all())
        return any(group in user_groups for group in allowed)
    return True


def can_access_note_content(user, note_content: NoteContent | None) -> bool:
    """按笔记所属的已登记仓库判断访问权限。"""

    if note_content is None:
        return False
    return can_access_note_repo(user, note_content.repo)
