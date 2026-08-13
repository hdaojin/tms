from contextlib import contextmanager
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import InMemoryStorage
from django.test import TestCase
from django.utils import timezone

from standards.models import SkillProject

from .models import ArchiveAsset, calculate_file_sha256


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

    def test_metadata_updates_do_not_rehash_but_file_replacement_does(self):
        with archive_in_memory_storage(), patch(
            "archives.models.calculate_file_sha256",
            wraps=calculate_file_sha256,
        ) as calculate_hash:
            project = SkillProject.objects.create(code="NSM", name="网络系统管理")
            asset = ArchiveAsset.objects.create(
                skill_project=project,
                title="原始资料",
                file=SimpleUploadedFile("original.txt", b"original", content_type="text/plain"),
            )
            self.assertEqual(calculate_hash.call_count, 1)

            asset.title = "新标题"
            asset.description = "更新描述"
            asset.metadata = {"version": 2}
            asset.is_locked = True
            asset.save()
            self.assertEqual(calculate_hash.call_count, 1)

            asset.file = SimpleUploadedFile("replacement.txt", b"replacement", content_type="text/plain")
            asset.save()
            self.assertEqual(calculate_hash.call_count, 2)
            self.assertEqual(asset.file_sha256, calculate_file_sha256(SimpleUploadedFile("check.txt", b"replacement")))

            asset.file_sha256 = ""
            asset.save()
            self.assertEqual(calculate_hash.call_count, 3)

    def test_update_fields_includes_hash_when_an_uploaded_file_is_replaced(self):
        with archive_in_memory_storage(), patch(
            "archives.models.calculate_file_sha256",
            wraps=calculate_file_sha256,
        ) as calculate_hash:
            project = SkillProject.objects.create(code="NSM", name="网络系统管理")
            asset = ArchiveAsset.objects.create(
                skill_project=project,
                title="资料",
                file=SimpleUploadedFile("original.txt", b"original", content_type="text/plain"),
            )
            asset.file = SimpleUploadedFile("replacement.txt", b"replacement", content_type="text/plain")
            asset.save(update_fields=["file"])

            self.assertEqual(calculate_hash.call_count, 2)
            asset.refresh_from_db()
            self.assertEqual(asset.file_sha256, calculate_file_sha256(SimpleUploadedFile("check.txt", b"replacement")))
