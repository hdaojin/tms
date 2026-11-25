import hashlib
import json
import re
from pathlib import PurePosixPath

from django.core.exceptions import PermissionDenied, ValidationError

from .log_sources import COACH, validate_body
from .models import TrainingTask
from notes.documents import NoteImages
from .teaching_notes import read_task_note, task_note_route


HEADING = re.compile(r"^ {0,3}##[ \t]+(.+?)\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def markdown_blocks(lines):
    """Keep fenced examples opaque and normalize their delimiters for markdown2."""
    lines = iter(lines)
    for line in lines:
        if line.lstrip().startswith("<!--") and "-->" not in line:
            comment = [line]
            for line in lines:
                comment.append(line)
                if "-->" in line:
                    break
            yield "\n".join(comment)
            continue
        opening = FENCE.match(line)
        if not opening:
            yield line
            continue
        code = []
        for line in lines:
            closing = FENCE.match(line)
            if closing and closing[1].startswith(opening[1]) and not closing[2].strip():
                break
            code.append(line)
        content = "\n".join(code)
        longest = max((len(run) for run in re.findall(r"`+", content)), default=0)
        delimiter = "`" * max(3, longest + 1)
        indent = " " * opening.start(1)
        yield f"{indent}{delimiter}{opening[2]}\n{content}\n{indent}{delimiter}"


def parse_teaching_note(markdown):
    """Extract the agreed ATX sections, preserving the teaching text as editable Markdown."""
    lines = markdown.lstrip("\ufeff").splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() in {"...", "---"}), None)
        if end is not None:
            lines = lines[end + 1 :]

    sections = []
    note_title = ""
    for line in markdown_blocks(lines):
        if not sections and not note_title and (primary := re.fullmatch(r" {0,3}#[ \t]+(.+?)\s*", line)):
            note_title = re.sub(r"[ \t]+#+$", "", primary[1]).strip()
        if heading := HEADING.fullmatch(line):
            title = re.sub(r"[ \t]+#+$", "", heading[1]).strip()
            if title == "教学附录":
                break
            sections.append((title, []))
            continue
        if sections:
            sections[-1][1].append(line)

    goals, outlines, titles, process = [], [], [], []
    for title, lines in sections:
        content = "\n".join(lines).strip("\n")
        if title == "训练目标":
            goals.append(content)
        elif title == "训练内容":
            outlines.append(content)
        else:
            titles.append(title)
            process.append(f"## {title}\n\n{content}".rstrip())
    return {
        "note_title": note_title,
        "note_goal": "\n\n".join(goals).strip(),
        "note_outline": "\n\n".join(outlines).strip() if outlines else numbered_outline(titles),
        "note_process": "\n\n".join(process),
    }


def numbered_outline(items):
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))


def can_refresh_note_images(previous, current):
    if not previous.get("note_image_format"):
        return any(row.get("note_images") or row.get("note_image_links") for row in current["tasks"])
    prior = {row["id"]: row.get("note_image_links", {}) for row in previous["tasks"]}
    return any(row.get("note_images", {}).keys() & prior.get(row["id"], {}).keys() for row in current["tasks"])


def build_note_draft(user, current_source, *, images=None, include_assets=True):
    """Decorate only the caller's currently authorized coach task rows with note snapshots."""
    if current_source["header"]["role"] != COACH:
        raise PermissionDenied
    entries = {entry["id"]: entry for entry in current_source["tasks"]}
    tasks = TrainingTask.objects.filter(pk__in=entries).order_by(
        "schedule_slot__starts_at", "training_plan_id", "order", "pk"
    )
    rows, warnings = [], []
    if images is None and include_assets:
        images = NoteImages()
    for task in tasks:
        entry = entries[task.pk].copy()
        entry.update(
            note_ref="",
            note_title="",
            note_goal=entry["goal"],
            note_outline=numbered_outline(entry["outline"]),
            note_process="",
        )
        issues = []
        if task_note_route(task.coach_link):
            try:
                ref, markdown, repo_slug, root, note_path = read_task_note(task, user, include_location=True)
            except ValidationError as exc:
                if getattr(exc, "code", None) == "note_too_large":
                    issues.append(exc.messages[0])
                else:
                    issues.append("教学笔记已不可读取，请核对关联或手写过程记录。")
            else:
                entry.update(parse_teaching_note(markdown), note_ref=ref)
                entry["note_title"] = entry["note_title"] or PurePosixPath(ref).stem
                if images is not None:
                    image_refs, image_links = images.snapshot(entry, repo_slug, root, note_path, issues)
                    if image_refs:
                        entry["note_images"] = image_refs
                    if image_links:
                        entry["note_image_links"] = image_links
                if not entry["note_goal"]:
                    issues.append("笔记缺少训练目标，请补写。")
                if not entry["note_process"]:
                    issues.append("笔记缺少教学环节，请补写过程记录。")
        else:
            issues.append("未关联教学笔记，请补写过程记录。")
        warning = " ".join(dict.fromkeys(issues))
        entry["note_warning"] = warning
        if warning:
            label = entry["title"] + (f"（{entry['note_title']}）" if entry["note_ref"] else "")
            warnings.append(f"{label}：{warning}")
        entry["version"] = hashlib.sha256(
            json.dumps(
                [
                    entry["version"],
                    entry["note_ref"],
                    entry["note_title"],
                    entry["note_goal"],
                    entry["note_outline"],
                    entry["note_process"],
                    *([entry["note_images"]] if entry.get("note_images") else []),
                    *([entry["note_image_links"]] if entry.get("note_image_links") else []),
                ],
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        rows.append(entry)

    source = {**current_source, "teaching_notes": True, "note_image_format": 1, "tasks": rows}
    body = {"achievement": "", "shortcomings": "", "improvement": ""}
    image_scopes = len(rows) > 1 and any(row.get("note_images") or row.get("note_image_links") for row in rows)
    for field, key in (("goals_md", "note_goal"), ("outline_md", "note_outline"), ("process", "note_process")):
        pieces = []
        for row in rows:
            if content := row[key]:
                if len(rows) > 1:
                    marker = f" <!--讲义任务 {row['id']}-->" if image_scopes else ""
                    content = f"# {row['period']} · {row['title']}{marker}\n\n{content}"
                pieces.append(content)
        body[field] = "\n\n".join(pieces)
    return source, validate_body(COACH, body, source, partial=True), warnings
