import shutil
import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from competition_standards.models import CompetitionType, Project, StandardModule, TrainingCycle

from .models import TrainingLog


TEST_MEDIA_ROOT = Path(tempfile.mkdtemp())
User = get_user_model()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class TrainingLogFileCleanupTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        competition_type = CompetitionType.objects.create(
            code="WSC-TL-CLEAN",
            name="训练日志清理测试赛事",
        )
        project = Project.objects.create(
            competition_type=competition_type,
            code="ITNSA-TL-CLEAN",
            name="训练日志清理测试项目",
        )
        self.module = StandardModule.objects.create(
            project=project,
            code="A",
            name="网络配置",
        )
        self.training_cycle = TrainingCycle.objects.create(
            code="TC-TL-CLEAN",
            name="训练日志清理测试周期",
            project=project,
            module_set=project.current_standard_module_set,
            start_date=date(2026, 1, 1),
        )
        self.user = User.objects.create_user(username="traininglog-cleanup", password="testpass123")

    def _upload(self, name: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, b"%PDF-1.4\ntraining log cleanup", content_type="application/pdf")

    def _create_log(self, filename: str = "training-log.pdf") -> TrainingLog:
        return TrainingLog.objects.create(
            training_cycle=self.training_cycle,
            module=self.module,
            task="文件清理测试任务",
            training_date=date(2026, 1, 2),
            file=self._upload(filename),
            uploaded_by=self.user,
        )

    def test_clearing_file_field_deletes_old_physical_file(self):
        training_log = self._create_log("clear-log.pdf")
        old_file_name = training_log.file.name
        storage = training_log.file.storage
        self.assertTrue(storage.exists(old_file_name))

        training_log.file = ""
        training_log.save()

        training_log.refresh_from_db()
        self.assertFalse(storage.exists(old_file_name))
        self.assertFalse(training_log.file.name)

    def test_replacing_file_deletes_old_physical_file(self):
        training_log = self._create_log("old-log.pdf")
        old_file_name = training_log.file.name
        storage = training_log.file.storage
        self.assertTrue(storage.exists(old_file_name))

        training_log.file = self._upload("new-log.docx")
        training_log.save()

        training_log.refresh_from_db()
        self.assertNotEqual(training_log.file.name, old_file_name)
        self.assertFalse(storage.exists(old_file_name))
        self.assertTrue(training_log.file.storage.exists(training_log.file.name))

    def test_deleting_training_log_deletes_physical_file(self):
        training_log = self._create_log("delete-log.pdf")
        file_name = training_log.file.name
        storage = training_log.file.storage
        self.assertTrue(storage.exists(file_name))

        training_log.delete()

        self.assertFalse(storage.exists(file_name))
