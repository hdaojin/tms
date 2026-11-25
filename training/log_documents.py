import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe

from core.documents.markdown import render_content_markdown
from core.documents.service import generate_document_pdf
from core.documents.types import DocumentAsset, DocumentInput

from .log_generation import ACTIVE, check_draft, source_for
from .log_sources import COACH, INLINE_DOCUMENT_FORMAT, changed_sources, check_source_access, validate_body
from .models import TrainingLog, TrainingLogDraft, TrainingLogGeneration
from .services import save_training_log


def note_section_html(markdown, tasks, origin):
    """Keep imported headings below the template's h3 and preserve their relative nesting."""
    # Typography may rewrite HTML comments. Keep the saved task markers opaque until resource resolution.
    markdown = re.sub(
        r"<!--讲义任务 (\d+)-->",
        r'<span data-document-section="\1"></span>',
        markdown,
    )
    def resolve_resources(html):
        soup = BeautifulSoup(html, "html.parser")
        grouped = len(tasks) > 1
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            level = int(heading.name[1])
            heading.name = f"h{min(6, max(4, level + (3 if grouped else 2)))}"
        for node in soup.find_all(id=True):
            del node["id"]
        by_task = {str(task["id"]): task for task in tasks if "id" in task}
        task = next(iter(by_task.values()), {}) if not grouped else {}
        for node in list(soup.descendants):
            if isinstance(node, Tag) and node.name == "span" and node.has_attr("data-document-section"):
                task = by_task.get(node["data-document-section"], {})
                node.extract()
            elif isinstance(node, Tag) and node.name == "img":
                src = node.get("src", "")
                if src.startswith("tms-asset:image-"):
                    continue
                if digest := task.get("note_images", {}).get(src):
                    node["src"] = f"tms-asset:{digest}"
                    continue
                if origin and (local_link := task.get("note_image_links", {}).get(src)):
                    src = urljoin(origin, local_link)
                caption = f"〔插图：{node.get('alt') or '见教学笔记'}〕"
                try:
                    link = urlsplit(src)
                    external = link.scheme in {"https", "http"} and link.hostname and not link.username and not link.password
                except ValueError:
                    external = False
                if external:
                    anchor = soup.new_tag("a", href=src)
                    anchor.string = caption
                    node.replace_with(anchor)
                else:
                    node.replace_with(caption)
        return str(soup)

    rendered = render_content_markdown(
        markdown, strict=True, document_assets=True, html_postprocessor=resolve_resources,
    )
    return mark_safe(rendered.html)


def document_input(data, images):
    source = data["source"]
    header = source["header"]
    coach = header["role"] == COACH
    title = "集训日志（教练）" if coach else f"选手日志（{header['author']}）"
    images = list(images)
    note_log = bool(source.get("teaching_notes"))
    if note_log:
        rows = source.get("note_image_rows", {})
        assets = {}
        for image in images:
            digest = rows.get(str(image.pk))
            if digest or source.get("editor"):
                assets[digest or f"image-{image.pk}"] = DocumentAsset(bytes(image.content), image.media_type)
    else:
        assets = {f"image-{image.pk}": DocumentAsset(bytes(image.content), image.media_type) for image in images}
    for name in ("school-logo", "worldskills-china"):
        path = finders.find(f"training/{name}.png")
        if not path:
            raise ValidationError("缺少日志模板页眉图片。")
        assets[name] = DocumentAsset(Path(path).read_bytes(), "image/png")
    # The document renderer sanitizes the complete fragment, including each Markdown cell.
    if note_log:
        note_sections = source.get("note_section_tasks", {})
        sections = {
            key: note_section_html(value, note_sections.get(key, source["tasks"]), data.get("origin", ""))
            for key, value in data["body"].items()
            if key != "task_title"
        }
    else:
        sections = {
            key: mark_safe(render_content_markdown(value, strict=True, document_assets=True).html)
            for key, value in data["body"].items()
            if key not in {"task_title", "suggested_items", "suggested_goals"}
        }
    compact_layout = note_log or source.get("editor") or source.get("document_format") == INLINE_DOCUMENT_FORMAT
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
                "task_title": data["body"].get("task_title") or "、".join(
                    dict.fromkeys(task["title"] for task in (
                        source["tasks"] if note_log or source.get("editor") else source["tasks"][:1]
                    ))
                ),
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


def draft_document(draft, *, origin=""):
    data = {"body": draft.body, "source": draft.source, "references": draft.references, "include_gallery": True}
    if origin and draft.source.get("teaching_notes"):
        data["origin"] = origin
    return data


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


def submit_draft(draft, revision, reviewed_source, accept_changes, *, origin=""):
    verify_submission(draft, revision, reviewed_source, accept_changes)
    data = draft_document(draft, origin=origin)
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
