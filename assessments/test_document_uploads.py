from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from core.code_validators import assessment_code_validator, module_code_validator, project_code_validator
from standards.models import SkillProject
from standards.forms import SkillProjectForm

from .document_uploads import DOCUMENT_FILENAME_TYPES, parse_document_version
from .forms import AssessmentDocumentForm, AssessmentForm, AssessmentModuleForm
from .models import Assessment, AssessmentDocument, AssessmentModule, AssessmentType
from .services import upload_assessment_document


class UploadFixture:
    def setUp(self):
        super().setUp()
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings = override_settings(PRIVATE_MEDIA_ROOT=self.directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_superuser(username="upload-owner", password="test")
        self.project = SkillProject.objects.create(code="ITNSA", name="网络系统管理")
        category = AssessmentType.objects.create(code="uploadtest", name="测试")
        self.assessment = Assessment.objects.create(
            code="WS2026",
            name="竞赛",
            skill_project=self.project,
            assessment_type=category,
            start_date=date(2026, 9, 5),
            created_by=self.user,
        )
        self.module = AssessmentModule.objects.create(assessment=self.assessment, code="A", name="模块A")

    def document(self, version="1.0", **kwargs):
        values = dict(
            assessment=self.assessment,
            module=self.module,
            document_type="test_project",
            version=version,
            document_date=date(2026, 9, 5),
            file=SimpleUploadedFile("原始资料.PDF", b"%PDF-1.4\n%%EOF", content_type="application/pdf"),
        )
        values.update(kwargs)
        return AssessmentDocument(**values)

    def upload(self, version="1.0", **kwargs):
        return upload_assessment_document(self.document(version, **kwargs), self.user)


class DocumentUploadTests(UploadFixture, TestCase):
    def test_filename_storage_snapshot_and_download(self):
        document = self.upload()
        expected = "WS2026-ITNSA-A-TestProject-v1.0-2026.09.05.pdf"
        self.assertEqual(document.filename, expected)
        self.assertEqual(Path(document.file.name).name, expected)
        self.assertEqual(document.file.name, f"WS2026/ITNSA/A/TestProject/{expected}")
        self.assertEqual(document.original_filename, "原始资料.PDF")
        self.assertEqual(document.numeric_version, Decimal("1.0"))
        self.assertIn("网络系统管理", document.title)
        self.assertEqual(len(document.file_sha256), 64)
        self.assessment.name = "Changed"
        self.assessment.save()
        document.refresh_from_db()
        self.assertEqual(document.filename, expected)
        self.client.force_login(self.user)
        for name in ("document_download", "document_preview"):
            response = self.client.get(reverse(f"assessments:{name}", args=[document.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertIn(expected, response["Content-Disposition"])
            response.close()

    def test_each_type_and_general_scope(self):
        for document_type, token in DOCUMENT_FILENAME_TYPES.items():
            with self.subTest(document_type=document_type):
                document = self.upload(document_type=document_type, module=None)
                self.assertEqual(document.filename, f"WS2026-ITNSA-GEN-{token}-v1.0-2026.09.05.pdf")
        self.upload()  # 模块与公共资料版本独立。

    def test_versions_increase_numerically_and_identical_content_is_allowed(self):
        first = self.upload("1.9")
        second = self.upload("2.0")
        self.assertEqual(first.file_sha256, second.file_sha256)
        for version in ("1.0", "1.9", "2.0", "02.0"):
            with self.subTest(version=version), self.assertRaises(ValidationError):
                self.upload(version, document_date=date(2026, 9, 6))
        self.upload("10.0")
        self.assertEqual(AssessmentDocument.objects.count(), 3)

    def test_invalid_version_syntax(self):
        for value in ("", "1", "1.00", "v1.0", "-1.0", "final", "0.9", "1e1", " 1.0", "１.０", "1.0\n"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_document_version(value)

    def test_code_boundaries_and_reserved_module(self):
        for validator, size in (
            (assessment_code_validator, 20),
            (project_code_validator, 12),
            (module_code_validator, 8),
        ):
            validator("A" * size)
            for code in ("", "A" * (size + 1), "中文", "A-B", "A_B", "A/B", "A\n"):
                with self.subTest(size=size, code=code), self.assertRaises(ValidationError):
                    validator(code)
        for code in ("GEN", "gen", "Gen"):
            with self.assertRaises(ValidationError):
                module_code_validator(code)

    def test_invalid_historical_code_blocks_new_upload(self):
        # 模拟上线前存在的不合规历史代码。
        SkillProject.objects.filter(pk=self.project.pk).update(code="old-code")
        with self.assertRaisesMessage(ValidationError, "请联系管理员检查历史代码"):
            self.upload()
        self.assertFalse(AssessmentDocument.objects.exists())

    def test_business_forms_reject_invalid_codes(self):
        for form_type in (AssessmentForm, AssessmentModuleForm, SkillProjectForm):
            with self.subTest(form=form_type.__name__):
                form = form_type(data={"code": "包含中文"})
                self.assertFalse(form.is_valid())
                self.assertIn("code", form.errors)

    def test_partial_storage_failure_cleans_its_file(self):
        with patch("assessments.storage.os.fsync", side_effect=OSError("disk failure")):
            with self.assertRaisesMessage(ValidationError, "文件写入失败"):
                self.upload()
        self.assertFalse(any(p.is_file() for p in Path(self.directory.name).rglob("*")))
        self.assertFalse(AssessmentDocument.objects.exists())

    def test_legacy_version_ignored_and_filename_unchanged(self):
        legacy = AssessmentDocument.objects.create(
            assessment=self.assessment,
            module=self.module,
            document_type="test_project",
            title="历史资料",
            file="legacy.pdf",
            original_filename="历史.pdf",
            file_sha256="a" * 64,
            version="999.0",
            uploaded_by=self.user,
        )
        self.upload("1.0")
        legacy.refresh_from_db()
        self.assertEqual(legacy.filename, "历史.pdf")
        self.assertEqual(legacy.version, "999.0")
        self.assertIsNone(legacy.numeric_version)

    def test_database_unique_version_for_both_scopes(self):
        for module in (None, self.module):
            saved = self.upload(module=module)
            with self.assertRaises(IntegrityError), transaction.atomic():
                AssessmentDocument.objects.create(
                    assessment=self.assessment,
                    module=module,
                    document_type="test_project",
                    numeric_version=Decimal("1.0"),
                    version="1.0",
                    uploaded_by=self.user,
                    file="duplicate.pdf",
                    file_sha256=saved.file_sha256,
                )

    def test_insert_failure_cleans_file(self):
        with patch.object(AssessmentDocument, "save", side_effect=IntegrityError("conflict")):
            with self.assertRaises(ValidationError):
                self.upload()
        self.assertFalse(any(p.is_file() for p in Path(self.directory.name).rglob("*")))
        self.assertFalse(AssessmentDocument.objects.exists())

    def test_existing_destination_is_not_overwritten_or_deleted(self):
        expected = "WS2026/ITNSA/A/TestProject/WS2026-ITNSA-A-TestProject-v1.0-2026.09.05.pdf"
        storage = AssessmentDocument._meta.get_field("file").storage
        path = Path(storage.path(expected))
        path.parent.mkdir(parents=True)
        path.write_bytes(b"existing file")
        with self.assertRaisesMessage(ValidationError, "目标文件已存在"):
            self.upload()
        self.assertEqual(path.read_bytes(), b"existing file")
        self.assertEqual(sum(p.is_file() for p in Path(self.directory.name).rglob("*")), 1)
        self.assertFalse(AssessmentDocument.objects.exists())

    def test_publish_race_cleans_temporary_file_and_preserves_winner(self):
        def another_writer_wins(source, destination):
            Path(destination).write_bytes(b"winner")
            raise FileExistsError("concurrent destination")

        with patch("assessments.storage.os.link", side_effect=another_writer_wins):
            with self.assertRaisesMessage(ValidationError, "目标文件已存在"):
                self.upload()
        files = [p for p in Path(self.directory.name).rglob("*") if p.is_file()]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), b"winner")
        self.assertFalse(AssessmentDocument.objects.exists())

    def test_old_uuid_file_remains_accessible(self):
        storage = AssessmentDocument._meta.get_field("file").storage
        old_name = "versions/old-key/old.pdf"
        path = Path(storage.path(old_name))
        path.parent.mkdir(parents=True)
        path.write_bytes(b"%PDF-1.4\n%%EOF")
        document = AssessmentDocument.objects.create(
            assessment=self.assessment, module=self.module, document_type="test_project",
            title="历史资料", file=old_name, original_filename="original.pdf",
            normalized_filename="old.pdf", file_sha256="a" * 64, uploaded_by=self.user,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("assessments:document_download", args=[document.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\n%%EOF")
        response.close()
        document.refresh_from_db()
        self.assertEqual(document.file.name, old_name)

    def test_permissions_and_module_mismatch(self):
        outsider = get_user_model().objects.create_user(username="outsider")
        with self.assertRaises(PermissionDenied):
            upload_assessment_document(self.document(), outsider)
        other = Assessment.objects.create(
            code="OTHER",
            name="另一场",
            skill_project=self.project,
            assessment_type=self.assessment.assessment_type,
            start_date=date(2026, 9, 5),
        )
        with self.assertRaises(ValidationError):
            self.upload(assessment=other)

    def test_form_and_http_validation(self):
        self.client.force_login(self.user)
        self.assertNotIn("title", AssessmentDocumentForm().fields)
        data = dict(
            assessment=self.assessment.pk,
            module=self.module.pk,
            document_type="test_project",
            version="1.0",
            document_date="2026-09-05",
        )
        data["file"] = self.document().file.file
        response = self.client.post(reverse("assessments:document_upload"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("assessments:assessment_detail", args=[self.assessment.pk]) + "?tab=modules"
        )
        data["file"] = self.document().file.file
        response = self.client.post(reverse("assessments:document_upload"), data)
        self.assertContains(response, "新版本必须更大")
        hint = self.client.get(
            reverse("assessments:document_version_hint"),
            {key: data[key] for key in ("assessment", "module", "document_type")},
        )
        self.assertContains(hint, "1.1")
        self.assertContains(hint, "1.0")

    def test_admin_add_uses_business_upload_and_existing_record_is_readonly(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin:assessments_assessmentdocument_add"))
        self.assertRedirects(response, reverse("assessments:document_upload"))
        document = self.upload()
        response = self.client.get(reverse("admin:assessments_assessmentdocument_change", args=[document.pk]))
        self.assertNotContains(response, 'name="file"')


class ConcurrentDocumentUploadTests(UploadFixture, TransactionTestCase):
    def test_same_version_concurrent_upload_does_not_duplicate_or_leave_files(self):
        barrier = Barrier(2)

        def attempt():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                document = self.document()
                barrier.wait(timeout=10)
                try:
                    upload_assessment_document(document, user)
                    return "saved"
                except ValidationError:
                    return "conflict"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sorted(results), ["conflict", "saved"])
        self.assertEqual(AssessmentDocument.objects.count(), 1)
        self.assertEqual(sum(p.is_file() for p in Path(self.directory.name).rglob("*")), 1)
