"""从站内教练任务链接读取已授权的 Markdown 笔记。"""

from urllib.parse import unquote, urlsplit

from django.core.exceptions import ValidationError
from django.urls import Resolver404, resolve

from core.documents.limits import MAX_CONTENT_BYTES
from notes.models import NoteRepo
from notes.paths import InvalidNotePathError, NoteNotFoundError, resolve_note_repo_root
from notes.permissions import can_access_note_repo
from notes.utils import resolve_note_markdown_path


def task_note_route(link):
    """只识别本站的笔记详情（仓库首页亦有 README 正文）。"""
    if not link.startswith("/") or link.startswith("//") or "\\" in link:
        return None
    try:
        path = unquote(urlsplit(link).path)
        route = resolve(path.rstrip("/") + "/")
    except (Resolver404, ValueError):
        return None
    if route.view_name in {"notes:note_detail", "notes:note_repo_index"}:
        return route
    return None


def normalize_task_note_link(link, request):
    """编辑时把同源的完整笔记 URL 转为可供后台读取的站内路径。"""
    if not link or link.startswith("/"):
        return link
    target = urlsplit(link)
    origin = urlsplit(request.build_absolute_uri("/"))
    default_ports = {"http": 80, "https": 443}
    try:
        target_port = target.port
    except ValueError:
        return link
    if (
        target.scheme != origin.scheme or target.hostname != origin.hostname
        or target.username is not None or target.password is not None
        or (target_port if target_port is not None else default_ports.get(target.scheme))
        != (origin.port if origin.port is not None else default_ports.get(origin.scheme))
    ):
        return link
    local = target._replace(scheme="", netloc="").geturl()
    return local if task_note_route(local) else link


def read_task_note(task, user, *, include_location=False):
    unavailable = "教学笔记已移动、不可读取或当前账号无权访问。"
    route = task_note_route(task.coach_link)
    if route is None or not user.is_active or not user.has_perm("notes.view_noterepo"):
        raise ValidationError(unavailable)
    repo = NoteRepo.objects.prefetch_related("allowed_groups").filter(slug=route.kwargs["repo"]).first()
    if repo is None or not can_access_note_repo(user, repo.slug, note_repo=repo):
        raise ValidationError(unavailable)
    try:
        root = resolve_note_repo_root(repo.relative_path)
        path = resolve_note_markdown_path(root, route.kwargs.get("slug"))
        relative = path.relative_to(root)
        if path.suffix.lower() != ".md" or any(part.startswith(".") for part in relative.parts):
            raise ValidationError(unavailable)
        with path.open("rb") as source:
            content = source.read(MAX_CONTENT_BYTES + 1)
        if len(content) > MAX_CONTENT_BYTES:
            raise ValidationError("教学笔记超过文档大小上限，请拆分授课单元。", code="note_too_large")
        result = (f"{repo.pk}/{relative.as_posix()}", content.decode("utf-8-sig"))
        return (*result, repo.slug, root, path) if include_location else result
    except (InvalidNotePathError, NoteNotFoundError, OSError, RuntimeError, ValueError) as exc:
        raise ValidationError(unavailable) from exc
