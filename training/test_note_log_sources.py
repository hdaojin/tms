import sys
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from pypdf import PdfReader
from PIL import Image

from core.documents.service import generate_document_pdf, render_document_html
from core.documents.types import DocumentInput
from core.documents.content import prepare_content
from notes.models import NoteRepo
from .log_documents import document_input, draft_document, source_digest
from .log_sources import COACH, changed_sources, check_source_access, collect_sources, validate_body
from .note_log_sources import build_note_draft, parse_teaching_note
from .note_log_drafts import import_note_draft
from notes.documents import NoteImages
from .models import TrainingLogDraft
from .test_process_refactor import ProcessFixture


EXAMPLE = """---
Title: Linux 命令结构与帮助查询
---
# Linux 命令结构与帮助查询

## 训练目标

- 能识别命令名、选项和操作数。
- 能为内建命令和外部命令选择帮助入口。

## 对照命令输出

比较 `ls /etc` 和 `ls -lh /etc` 的输出。

### 随堂练习

~~~bash
## 教学附录
ls -lh /etc
~~~

## 为命令选择帮助入口

使用 `help cd` 和 `man ls` 查询用法。

## 教学附录

教师用参考答案。
"""


def example_document(*, long=False):
    parts = parse_teaching_note(EXAMPLE)
    source = {
        "teaching_notes": True,
        "format": 2,
        "header": {"role": COACH, "author": "授课教练", "heading": "Linux 系统管理", "date": "2026-01-01"},
        "tasks": [{"title": "命令行基础", "goal": "", "outline": [], "domains": ["Linux"]}],
    }
    body = {
        "goals_md": parts["note_goal"],
        "outline_md": parts["note_outline"],
        "process": parts["note_process"],
        "achievement": "两名选手已填报。",
        "shortcomings": "还有一人未填报。",
        "improvement": "下次课核对帮助命令的使用。",
    }
    if long:
        body["process"] += "\n\n" + "\n\n".join(f"练习 {i}：记录命令与输出。" for i in range(65))
    return document_input({"source": source, "body": body}, [])


def test_note_outline_headings_code_and_appendix():
    parts = parse_teaching_note(EXAMPLE)
    assert parts["note_outline"] == "1. 对照命令输出\n2. 为命令选择帮助入口"
    assert "教师用参考答案" not in parts["note_process"]
    document = BeautifulSoup(render_document_html(example_document()), "html.parser")
    assert [h.get_text() for h in document.select("#log-process h4")] == ["对照命令输出", "为命令选择帮助入口"]
    assert document.select_one("#log-process h5").get_text() == "随堂练习"
    assert "## 教学附录" in document.select_one("#log-process pre code").get_text()
    assert len(document.select("#log-goals li")) == 2
    assert len(document.select("#log-outline li")) == 2
    assert len(document.select("#log-logos img")) == 2
    assert "授课教练" in document.select_one("#log-signature").get_text()


def test_explicit_outline_and_incomplete_note():
    note = EXAMPLE.replace("## 对照命令输出", "## 训练内容\n\n- 核心训练内容\n\n## 对照命令输出")
    assert parse_teaching_note(note)["note_outline"] == "- 核心训练内容"
    assert parse_teaching_note("# 课名\n\n## 教学附录\n\n## 备用题") == {
        "note_title": "课名",
        "note_goal": "",
        "note_outline": "",
        "note_process": "",
    }


def test_many_image_references_and_invalid_file(tmp_path):
    note = tmp_path / "lesson.md"
    image = tmp_path / "screen.png"
    image.write_bytes(b"not an image")
    row = {"note_process": "![界面](screen.png)", "note_goal": "", "note_outline": ""}
    warnings = []
    refs, links = NoteImages().snapshot(row, "linux", tmp_path, note, warnings)
    assert not refs and not links
    assert warnings and "无法解码" in warnings[0]
    Image.new("RGB", (10, 10), "red").save(image)
    row["note_process"] = "\n\n".join(["![界面](screen.png)"] * 29)
    collector = NoteImages()
    refs, links = collector.snapshot(row, "linux", tmp_path, note, [])
    digest = refs["screen.png"]
    document = DocumentInput(
        title="讲义", content=row["note_process"].replace("screen.png", f"tms-asset:{digest}"),
        assets={digest: collector.assets[digest][0]},
    )
    assert not links
    assert len(BeautifulSoup(render_document_html(document), "html.parser").find_all("img")) == 29


@pytest.mark.document_pdf_native
def test_note_pdf_pagination():
    if sys.platform != "linux":
        pytest.skip("原生 PDF 渲染需要 Linux")
    pdf = PdfReader(BytesIO(generate_document_pdf(example_document(long=True))))
    assert len(pdf.pages) >= 2
    text = "".join(page.extract_text() for page in pdf.pages)
    for phrase in ("授课教练", "训练目标", "随堂练习", "改进方向"):
        assert phrase in text
    assert "教师用参考答案" not in text


class NoteLogSourcesTests(ProcessFixture, TestCase):
    def test_images_bound_to_each_note_and_archived_in_private_draft(self):
        with TemporaryDirectory() as temp, self.settings(NOTES_ROOT=temp):
            root = Path(temp) / "debian"
            repo = NoteRepo.objects.create(slug="debian", relative_path="debian", title="系统管理")
            self.coach.user_permissions.add(Permission.objects.get(codename="view_noterepo"))
            self.cycle_obj.status = "active"
            self.cycle_obj.save()
            self.cycle_obj.members.update(is_current=True)
            for slot, name, color in [(self.slot, "morning", "blue"), (self.other_slot(), "afternoon", "red")]:
                folder = root / name
                folder.mkdir(parents=True)
                Image.new("RGB", (20, 10), color).save(folder / "实验.png")
                (folder / "diagram.svg").write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10">'
                    '<rect width="20" height="10" fill="red"/></svg>',
                    encoding="utf-8",
                )
                (folder / "lesson.md").write_text(
                    EXAMPLE.replace(
                        "## 为命令选择帮助入口",
                        "![界面](实验.png)\n\n![外部截图](https://example.com/other.png)\n\n"
                        "![越界](../../outside.png)\n\n![拓扑图](diagram.svg)\n\n"
                        "`![代码](missing.png)`\n\n## 为命令选择帮助入口",
                    ),
                    encoding="utf-8",
                )
                task = self.task(slot=slot, title=name)
                task.coach_link = f"/notes/{repo.slug}/{name}/lesson/"
                task.save(update_fields=["coach_link"])
            draft = TrainingLogDraft.objects.create(
                author=self.coach, cycle=self.cycle_obj, training_date=self.slot.day.date
            )
            current, _, _ = collect_sources(self.coach, self.cycle_obj, self.slot.day.date)
            snapshot, _, warnings = build_note_draft(self.coach, current)
            self.assertIn("越界", " ".join(warnings))
            self.assertNotIn("missing.png", " ".join(warnings))
            draft = import_note_draft(draft, draft.revision, source_digest(snapshot))
            self.assertEqual(draft.images.count(), 3)
            first, second = [row["note_images"]["实验.png"] for row in draft.source["tasks"]]
            self.assertNotEqual(first, second)
            data = document_input(draft_document(draft, origin="https://tms.example/"), draft.images.all())
            html = BeautifulSoup(data.content, "html.parser")
            self.assertEqual(
                [img["src"] for img in html.select('#log-process img[alt="界面"]')],
                [f"tms-asset:{first}", f"tms-asset:{second}"],
            )
            self.assertEqual(len(html.select('a[href="https://example.com/other.png"]')), 2)
            pdf_html, assets = prepare_content(data, for_pdf=True)
            svg_tags = pdf_html.select('img[alt="拓扑图"]')
            self.assertEqual(len(svg_tags), 2)
            self.assertTrue(all(assets[img["src"]][1] == "image/svg+xml" for img in svg_tags))
            rendered = BeautifulSoup(render_document_html(data), "html.parser")
            self.assertTrue(
                all(img["src"].startswith("data:image/svg+xml;base64,") for img in rendered.select('img[alt="拓扑图"]'))
            )
            (root / "morning" / "实验.png").unlink()
            fresh, _, _ = build_note_draft(self.coach, current)
            self.assertTrue(changed_sources(snapshot, fresh))
            self.assertEqual(
                render_document_html(data),
                render_document_html(
                    document_input(draft_document(draft, origin="https://tms.example/"), draft.images.all())
                ),
            )

    def test_multi_task_fallback_snapshot_and_revocation(self):
        with TemporaryDirectory() as temp, self.settings(NOTES_ROOT=temp):
            root = Path(temp) / "debian"
            root.mkdir()
            note = root / "command-line.md"
            note.write_text(EXAMPLE, encoding="utf-8")
            repo = NoteRepo.objects.create(slug="debian", relative_path="debian", title="系统管理")
            self.coach.user_permissions.add(Permission.objects.get(codename="view_noterepo"))
            self.cycle_obj.status = "active"
            self.cycle_obj.save()
            self.cycle_obj.members.update(is_current=True)
            task = self.task(title="命令行结构")
            task.coach_link = f"/notes/{repo.slug}/command-line/"
            task.save(update_fields=["coach_link"])
            second = self.task(
                slot=self.other_slot(), title="独立实训", requirements="完成任务", subtask_titles=["验证输出"]
            )
            current, _, _ = collect_sources(self.coach, self.cycle_obj, self.slot.day.date)
            source, body, warnings = build_note_draft(self.coach, current)
            self.assertEqual([entry["id"] for entry in source["tasks"]], [task.pk, second.pk])
            self.assertEqual(len(warnings), 1)
            self.assertIn("独立实训", warnings[0])
            self.assertIn("完成任务", body["goals_md"])
            self.assertIn("验证输出", body["outline_md"])
            self.assertNotIn("teaching_notes", current)
            validate_body(COACH, body, source, partial=True)
            with self.assertRaises(ValidationError):
                validate_body(COACH, body, source)
            note.write_text(EXAMPLE.replace("对照命令输出", "比较命令输出"), encoding="utf-8")
            revised, _, _ = build_note_draft(self.coach, current)
            check_source_access(source, revised)
            self.assertEqual(len(changed_sources(source, revised)), 1)
            self.assertIn("对照命令输出", body["process"])
            repo.is_visible = False
            repo.save()
            revoked, _, _ = build_note_draft(self.coach, current)
            with self.assertRaisesMessage(ValidationError, "教学笔记已不在可用范围"):
                check_source_access(source, revoked)
            with self.assertRaises(PermissionDenied):
                build_note_draft(self.student, {"header": {"role": "competitor"}, "tasks": []})
