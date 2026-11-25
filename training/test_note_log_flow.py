from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bs4 import BeautifulSoup
from notes.models import NoteRepo
from PIL import Image

from .log_sources import COACH, editor_fields
from .models import TrainingLog, TrainingLogDraft
from .test_process_refactor import ProcessFixture


class TeachingNoteLogFlowTests(ProcessFixture, TestCase):
    def setUp(self):
        super().setUp()
        files = TemporaryDirectory()
        self.addCleanup(files.cleanup)
        self.root = Path(files.name)
        self.enterContext(override_settings(NOTES_ROOT=self.root, PRIVATE_MEDIA_ROOT=self.root))
        self.repo = NoteRepo.objects.create(slug="linux", title="Linux 讲义", relative_path="linux")
        directory = self.root / "linux"
        directory.mkdir()
        self.note = directory / "lesson.md"
        self.note.write_text(
            "# Linux 命令\n\n## 训练目标\n\n掌握查询方法。\n\n## 查询帮助\n\n使用 `man ls`。\n\n"
            "## 教学附录\n\n备用答案。\n", encoding="utf-8",
        )
        self.coach.user_permissions.add(Permission.objects.get(codename="view_noterepo"))
        self.task(coach_link="/notes/linux/lesson/")
        self.cycle_obj.status = "active"
        self.cycle_obj.save()
        self.cycle_obj.members.filter(user=self.coach).update(is_current=True)
        self.client.force_login(self.coach)
        self.start = reverse("training:log_ai_start")

    def import_form(self):
        page = self.client.get(self.start)
        self.assertContains(page, "从教学笔记生成")
        candidates = self.client.get(f"{self.start}?note_candidates=1")
        self.assertContains(candidates, "采用所选笔记区块")
        self.assertFalse(TrainingLogDraft.objects.exists())
        return {
            **dict.fromkeys(dict(editor_fields(COACH)), ""),
            "note_digest": candidates.context["note_digest"], "revision": 0, "editor": "1",
            "action": "note_apply", "note_sections": ["goals_md", "outline_md", "process"],
        }

    def test_manual_preview_edit_archive_download(self):
        page = self.client.post(self.start, self.import_form(), follow=True)
        self.assertContains(page, "编辑正文")
        draft = TrainingLogDraft.objects.get(author=self.coach)
        self.assertIn("man ls", draft.body["process"])
        self.assertNotIn("备用答案", str(draft.body))
        url = reverse("training:log_ai_draft", args=[draft.pk])
        preview = self.client.get(reverse("training:log_ai_preview", args=[draft.pk]))
        self.assertContains(preview, "查询帮助")
        self.assertContains(preview, "掌握查询方法")
        form = {**draft.body, "achievement": "根据课堂记录已完成练习。", "shortcomings": "帮助查询仍需练习。",
                "improvement": "下次增加查询练习。", "revision": draft.revision, "action": "edit", "editor": "1"}
        page = self.client.post(url, form, follow=True)
        self.assertContains(page, "下次增加查询练习")
        draft.refresh_from_db()
        data = {
            **draft.body, "action": "submit", "editor": "1", "revision": draft.revision,
            "source_digest": page.context["source_digest"],
        }
        with patch("training.log_documents.generate_document_pdf", return_value=b"%PDF-1.4\n"):
            self.client.post(url, data)
        log = TrainingLog.objects.get(author=self.coach, training_date=timezone.localdate())
        self.assertEqual(log.online_document["body"]["process"], draft.body["process"])
        self.assertContains(self.client.get(reverse("training:log_list")), reverse("training:log_detail", args=[log.pk]))
        download = self.client.get(reverse("training:log_download", args=[log.pk]))
        self.assertEqual(b"".join(download.streaming_content), b"%PDF-1.4\n")
        self.client.post(url, data)
        self.assertEqual(TrainingLog.objects.count(), 1)

    def test_preview_change_requires_review_and_revoked_access_hides_text(self):
        form = self.import_form()
        self.note.write_text(self.note.read_text(encoding="utf-8").replace("man ls", "man cd"), encoding="utf-8")
        page = self.client.post(self.start, form)
        self.assertContains(page, "重新核对预览")
        draft = TrainingLogDraft.objects.get()
        self.assertEqual(draft.body, {})
        candidates = self.client.get(f"{self.start}?note_candidates=1")
        form["note_digest"] = candidates.context["note_digest"]
        self.client.post(self.start, form)
        self.coach.user_permissions.remove(Permission.objects.get(codename="view_noterepo"))
        page = self.client.get(reverse("training:log_ai_draft", args=[draft.pk]))
        self.assertNotContains(page, "掌握查询方法")
        preview = self.client.get(reverse("training:log_ai_preview", args=[draft.pk]))
        self.assertEqual(preview.status_code, 400)
        draft.refresh_from_db()
        url = reverse("training:log_ai_draft", args=[draft.pk])
        rebuild = {"revision": draft.revision, "action": "note_rebuild", "source_digest": page.context["source_digest"]}
        self.assertContains(self.client.post(url, rebuild), "请确认按当前可用素材")
        page = self.client.post(url, {**rebuild, "accept_changes": "on"}, follow=True)
        self.assertContains(page, "编辑正文")
        self.assertNotContains(page, "掌握查询方法")

    def test_importing_a_new_goal_keeps_existing_process_image_snapshot(self):
        image = self.note.with_name("screen.png")
        Image.new("RGB", (10, 10), "red").save(image)
        self.note.write_text(
            "# Linux 命令\n\n## 训练目标\n\n原目标\n\n## 查询帮助\n\n![练习截图](screen.png)",
            encoding="utf-8",
        )
        self.assertEqual(self.client.post(self.start, self.import_form()).status_code, 302)
        draft = TrainingLogDraft.objects.get(author=self.coach)
        url = reverse("training:log_ai_draft", args=[draft.pk])
        preview_url = reverse("training:log_ai_preview", args=[draft.pk])
        preview = BeautifulSoup(self.client.get(preview_url).content, "html.parser")
        original = preview.select_one('#log-process img[alt="练习截图"]')["src"]

        Image.new("RGB", (10, 10), "blue").save(image)
        self.note.write_text(self.note.read_text(encoding="utf-8").replace("原目标", "新目标"), encoding="utf-8")
        candidates = self.client.get(f"{url}?note_candidates=1")
        self.assertEqual(self.client.post(url, {
            **draft.body, "editor": "1", "action": "note_apply", "revision": draft.revision,
            "note_digest": candidates.context["note_digest"], "note_sections": ["goals_md"],
        }).status_code, 302)
        preview = BeautifulSoup(self.client.get(preview_url).content, "html.parser")
        self.assertIn("新目标", preview.select_one("#log-goals").get_text())
        self.assertEqual(preview.select_one('#log-process img[alt="练习截图"]')["src"], original)
