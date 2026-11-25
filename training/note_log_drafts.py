from django.core.exceptions import ValidationError
from django.db import transaction

from . import log_generation
from .log_documents import source_digest
from .log_sources import COACH, check_source_access, collect_sources, editor_body, validate_editor_body
from .models import TrainingLogGeneration, TrainingLogImage
from notes.documents import NoteImages
from .note_log_sources import build_note_draft, can_refresh_note_images


NOTE_SECTIONS = ("goals_md", "outline_md", "process")


def image_sources(source):
    return [
        {"id": row["id"], "note_images": row.get("note_images", {}), "note_image_links": row.get("note_image_links", {})}
        for row in source["tasks"]
    ]


@transaction.atomic
def import_note_draft(draft, revision, reviewed_source, *, rebuild=False, sections=None):
    draft = log_generation.lock_draft(draft)
    if draft.revision != revision:
        raise ValidationError("草稿已更新，请重新预览。")
    pending = (*log_generation.ACTIVE, TrainingLogGeneration.Status.READY, TrainingLogGeneration.Status.REVIEW)
    if TrainingLogGeneration.objects.filter(draft=draft, status__in=pending).exists():
        raise ValidationError("请先处理当前生成任务。")
    current, _, missing = collect_sources(draft.author, draft.cycle, draft.training_date)
    if current["header"]["role"] != COACH or missing:
        raise ValidationError(missing or "仅授课教练可从教学笔记生成日志。")
    images = NoteImages()
    snapshot, body, _ = build_note_draft(draft.author, current, images=images)
    if source_digest(snapshot) != reviewed_source:
        raise ValidationError("教学笔记或任务进度已变化，请重新核对预览。")
    if sections is not None:
        if draft.source:
            check_source_access(draft.source, snapshot)
        available = {key for key in NOTE_SECTIONS if body[key].strip()}
        if not any(row["note_ref"] for row in snapshot["tasks"]) or not sections or not set(sections) <= available:
            raise ValidationError("请选择有内容的教学笔记区块。")
        previous = editor_body(COACH, draft.source or current, draft.body)
        body = {**previous, **{key: body[key] for key in sections}}
        snapshot["editor"] = True
        previous_images = draft.source.get("note_section_tasks", {})
        previous_tasks = image_sources(draft.source) if draft.source.get("teaching_notes") else []
        new_tasks = image_sources(snapshot)
        snapshot["note_section_tasks"] = {
            key: new_tasks if key in sections else previous_images.get(key, previous_tasks)
            for key in NOTE_SECTIONS
        }
        body = validate_editor_body(COACH, body, snapshot, partial=True)
    elif draft.source.get("teaching_notes"):
        if rebuild:
            try:
                check_source_access(draft.source, snapshot)
            except ValidationError:
                pass
            else:
                if not can_refresh_note_images(draft.source, snapshot):
                    raise ValidationError("草稿仍可编辑，请保留已有正文。")
        else:
            check_source_access(draft.source, snapshot)
            return draft
    elif draft.body:
        raise ValidationError("当天已有正文，请继续编辑已有草稿。")
    # These private snapshots survive source-file edits and are also used by the archived preview.
    if rebuild:
        draft.images.filter(pk__in=draft.source.get("note_image_rows", {})).delete()
    image_rows = {} if rebuild else draft.source.get("note_image_rows", {}).copy()
    known = set(image_rows.values())
    new_assets = {digest: asset for digest, asset in images.assets.items() if digest not in known}
    stored_images = TrainingLogImage.objects.bulk_create(
        [
            TrainingLogImage(draft=draft, caption=caption, media_type=asset.media_type, content=asset.content)
            for asset, caption in new_assets.values()
        ]
    )
    image_rows.update((str(image.pk), digest) for image, digest in zip(stored_images, new_assets, strict=True))
    if image_rows:
        snapshot["note_image_rows"] = image_rows
    draft.source, draft.body = snapshot, body
    draft.revision += 1
    draft.save(update_fields=["source", "body", "revision", "updated_at"])
    return draft
