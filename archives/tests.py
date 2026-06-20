from contextlib import contextmanager

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import InMemoryStorage
from django.test import TestCase
from django.utils import timezone

from standards.models import SkillProject

from .models import ArchiveAsset


@contextmanager
def archive_in_memory_storage():
    field = ArchiveAsset._meta.get_field("file")
    original_storage = field.storage
    field.storage = InMemoryStorage()
    try:
        yield
    finally:
        field.storage = original_storage


class ArchiveAssetTests(TestCase):
    def test_asset_records_file_metadata_and_business_path(self):
        with archive_in_memory_storage():
            project = SkillProject.objects.create(code="NSM", name="网络系统管理")

            asset = ArchiveAsset.objects.create(
                skill_project=project,
                asset_type=ArchiveAsset.AssetType.TEST_PROJECT,
                title="Module A 试题",
                file=SimpleUploadedFile("module-a.txt", b"hello", content_type="text/plain"),
                business_date=timezone.localdate(),
            )

            self.assertEqual(asset.original_filename, "module-a.txt")
            self.assertEqual(asset.file_sha256, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
            self.assertIn("test_project", asset.file.name)
            self.assertIn(timezone.localdate().strftime("%Y/%m"), asset.file.name)
