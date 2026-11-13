import hashlib
import json
from pathlib import Path

from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe

from core.documents.content import MARKDOWN_EXTRAS
from core.documents.service import generate_document_pdf
from core.documents.types import DocumentAsset, DocumentInput
from core.utils.markdown import render_markdown_text

from .log_generation import ACTIVE, check_draft, source_for
from .log_sources import COACH, INLINE_DOCUMENT_FORMAT, changed_sources, check_source_access, validate_body
from .models import TrainingLog, TrainingLogDraft, TrainingLogGeneration
from .services import save_training_log


def document_input(data, images):
    source = data["source"]
    header = source["header"]
    coach = header["role"] == COACH
    title = "集训日志（教练）" if coach else f"选手日志（{header['author']}）"
    images = list(images)
    assets = {f"image-{image.pk}": DocumentAsset(bytes(image.content), image.media_type) for image in images}
    for name in ("school-logo", "worldskills-china"):
        path = finders.find(f"training/{name}.png")
        if not path:
            raise ValidationError("缺少日志模板页眉图片。")
        assets[name] = DocumentAsset(Path(path).read_bytes(), "image/png")
    # The document renderer sanitizes the complete fragment, including each Markdown cell.
    sections = {
        key: mark_safe(render_markdown_text(value, extensions=MARKDOWN_EXTRAS, strict=True).html)
        for key, value in data["body"].items()
        if key not in {"task_title", "suggested_items", "suggested_goals"}
    }
    compact_layout = source.get("document_format") == INLINE_DOCUMENT_FORMAT
    new_layout = compact_layout or source.get("format") == 2
    modules = {}
    if not new_layout:
        for task in source["tasks"]:
            plan = modules.setdefault(task["plan_id"], {"title": task["plan"], "periods": {}})
            plan["periods"][f"{task['period']} {task['module']}"] = None
    gallery = (
        [
            image.pk
            for image in images
            if not any(f'src="tms-asset:image-{image.pk}"' in section for section in sections.values())
        ]
        if data.get("include_gallery") and not compact_layout
        else []
    )
    return DocumentInput(
        title=f"{header['heading']}{title}" if new_layout else title,
        template_id="training-log",
        content_format="html_fragment",
        assets=assets,
        content=render_to_string(
            "training/log_document.html",
            {
                "source": source,
                "header": header,
                "heading": title,
                "coach": coach,
                "sections": sections,
                "modules": modules.values(),
                "new_layout": new_layout,
                "compact_layout": compact_layout,
                "domains": dict.fromkeys(domain for task in source["tasks"] for domain in task.get("domains", [])),
                "task_title": data["body"].get("task_title") or source["tasks"][0]["title"],
                "suggested_items": data["body"].get("suggested_items", []),
                "goals": [
                    (
                        task["title"],
                        task["goal"] or data["body"].get("suggested_goals", {}).get(str(task.get("id")), ""),
                        not task["goal"],
                    )
                    for task in source["tasks"]
                ]
                if coach
                else [],
                "gallery": gallery,
                "references": data.get("references", "").splitlines(),
            },
        ),
    )


def source_digest(source):
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def draft_document(draft):
    return {"body": draft.body, "source": draft.source, "references": draft.references, "include_gallery": True}


def verify_submission(draft, revision, reviewed_source, accept_changes):
    check_draft(draft)
    if draft.revision != revision:
        raise ValidationError("草稿版本已变化，请重新预览。")
    if TrainingLogGeneration.objects.filter(draft=draft, status__in=ACTIVE).exists():
        raise ValidationError("正文仍在生成，请在生成结束后提交。")
    current, _, _ = source_for(draft)
    check_source_access(draft.source, current)
    if reviewed_source != source_digest(current):
        raise ValidationError("训练素材已更新，请重新查看并确认。")
    if changed_sources(draft.source, current) and not accept_changes:
        raise ValidationError("请确认使用已审阅的正文，或根据更新后的素材重新生成。")
    validate_body(draft.source["header"]["role"], draft.body, draft.source)


def submit_draft(draft, revision, reviewed_source, accept_changes):
    verify_submission(draft, revision, reviewed_source, accept_changes)
    data = draft_document(draft)
    pdf = generate_document_pdf(document_input(data, draft.images.all()))
    log = TrainingLog(
        author=draft.author,
        training_cycle=draft.cycle,
        training_date=draft.training_date,
        online_document=data,
        document=ContentFile(pdf, name="训练日志.pdf"),
    )
    executions = (
        []
        if data["source"]["header"]["role"] == COACH
        else [pk for task in data["source"]["tasks"] for pk in task["execution_ids"]]
    )

    def finalize(saved):
        locked = TrainingLogDraft.objects.select_for_update().get(pk=draft.pk)
        # The new formal log exists inside this transaction. Check the remaining invariants directly.
        current, _, _ = source_for(locked)
        check_source_access(locked.source, current)
        if locked.submitted_log_id or locked.revision != revision or source_digest(current) != reviewed_source:
            raise ValidationError("草稿或训练素材已变化，请重新预览。")
        if TrainingLogGeneration.objects.filter(draft=locked, status__in=ACTIVE).exists():
            raise ValidationError("正文仍在生成，请在生成结束后提交。")
        locked.submitted_log = saved
        locked.save(update_fields=["submitted_log", "updated_at"])
        TrainingLogGeneration.objects.filter(draft=locked).delete()

    save_training_log(log, executions, backfill=draft.training_date < timezone.localdate(), finalize=finalize)
    return log
