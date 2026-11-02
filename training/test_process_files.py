from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import process
from .test_process_refactor import ProcessFixture


class TrainingProcessFileTests(ProcessFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.storage_settings = override_settings(PRIVATE_MEDIA_ROOT=self.directory.name)
        self.storage_settings.enable()
        self.addCleanup(self.storage_settings.disable)

    def test_task_and_progress_files_have_separate_authorization(self):
        task = self.task(
            assign_all=False, competitors=[self.student.pk], attachments=[SimpleUploadedFile("指导.txt", b"guide")]
        )
        execution = task.executions.get()
        progress = process.save_progress(
            execution,
            self.student,
            completed="完成",
            problems="",
            files=[SimpleUploadedFile("进度.txt", b"private progress")],
        )
        guide = task.attachments.get()
        attachment = progress.attachments.get()
        self.assertNotEqual(guide.file.name, attachment.file.name)
        for user, allowed in ((self.student, True), (self.coach, True), (self.student2, False), (self.other, False)):
            self.client.force_login(user)
            for kind, item in (("task", guide), ("progress", attachment)):
                response = self.client.get(reverse("training:attachment_download", args=[kind, item.pk]))
                self.assertEqual(response.status_code, 200 if allowed else 403)
                response.close()

    def test_invalid_file_rolls_back_progress_and_never_writes_earlier_file(self):
        execution = self.task().executions.get(user=self.student)
        with self.assertRaises(ValidationError):
            process.save_progress(
                execution,
                self.student,
                completed="内容",
                problems="",
                files=[SimpleUploadedFile("有效.txt", b"valid"), SimpleUploadedFile("非法.exe", b"bad")],
            )
        self.assertFalse(execution.progress_records.exists())
        self.assertEqual(list(Path(self.directory.name).rglob("*.txt")), [])

    def test_progress_file_replacement_and_delete_clean_only_after_commit(self):
        execution = self.task().executions.get(user=self.student)
        progress = process.save_progress(
            execution, self.student, completed="内容", problems="", files=[SimpleUploadedFile("旧文件.txt", b"old")]
        )
        attachment = progress.attachments.get()
        storage, old_name = attachment.file.storage, attachment.file.name
        with self.captureOnCommitCallbacks(execute=True):
            attachment.file = SimpleUploadedFile("新文件.txt", b"new")
            attachment.save()
            self.assertTrue(storage.exists(old_name))
        self.assertFalse(storage.exists(old_name))
        new_name = attachment.file.name
        with self.captureOnCommitCallbacks(execute=True):
            attachment.delete()
            self.assertTrue(storage.exists(new_name))
        self.assertFalse(storage.exists(new_name))
