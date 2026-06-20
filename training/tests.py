import zipfile
from contextlib import contextmanager
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import InMemoryStorage
from django.test import TestCase
from django.utils import timezone

from standards.models import CapabilityDomain, SkillProject

from archives.models import ArchiveAsset

from .models import TrainingCycle, TrainingLog
from .services import build_training_log_archive, create_training_log_asset


@contextmanager
def archive_in_memory_storage():
    field = ArchiveAsset._meta.get_field("file")
    original_storage = field.storage
    field.storage = InMemoryStorage()
    try:
        yield
    finally:
        field.storage = original_storage


class TrainingLogArchiveTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="competitor")
        self.project = SkillProject.objects.create(code="NSM", name="网络系统管理")
        self.domain = CapabilityDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.cycle = TrainingCycle.objects.create(
            skill_project=self.project,
            code="2026-SPRING",
            name="2026 春季训练",
            start_date=timezone.localdate(),
        )

    def test_training_log_creates_archive_asset_and_zip_export(self):
        with archive_in_memory_storage():
            log = TrainingLog.objects.create(
                training_cycle=self.cycle,
                capability_domain=self.domain,
                training_date=timezone.localdate(),
                uploaded_by=self.user,
                topic="SSH 排错",
            )
            create_training_log_asset(
                log,
                SimpleUploadedFile("ssh.txt", b"training log", content_type="text/plain"),
                user=self.user,
            )
            log.refresh_from_db()

            asset = log.primary_asset
            self.assertIsNotNone(asset)
            self.assertEqual(asset.asset_type, "training_log")
            self.assertIn("training_log", asset.file.name)
            self.assertIn("training-traininglog", asset.file.name)

            data = build_training_log_archive(TrainingLog.objects.filter(pk=log.pk))
            with zipfile.ZipFile(BytesIO(data)) as archive:
                self.assertEqual(len(archive.namelist()), 1)
                self.assertIn("ssh.txt", archive.namelist()[0])
                self.assertEqual(archive.read(archive.namelist()[0]), b"training log")
