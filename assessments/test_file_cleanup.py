import shutil
import tempfile
from datetime import date
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from competition_standards.models import CompetitionType, Project, StandardModule, TrainingCycle

from .models import Assessment, AssessmentAttachment, AssessmentModule


TEST_PRIVATE_MEDIA_ROOT = Path(tempfile.mkdtemp())


@override_settings(PRIVATE_MEDIA_ROOT=TEST_PRIVATE_MEDIA_ROOT)
class AssessmentFileCleanupTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_PRIVATE_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        competition_type = CompetitionType.objects.create(
            code="WSC-AM-CLEAN",
            name="考核资料清理测试赛事",
        )
        project = Project.objects.create(
            competition_type=competition_type,
            code="ITNSA-AM-CLEAN",
            name="考核资料清理测试项目",
        )
        self.module = StandardModule.objects.create(
            project=project,
            code="A",
            name="网络配置",
        )
        training_cycle = TrainingCycle.objects.create(
            code="TC-AM-CLEAN",
            name="考核资料清理测试周期",
            project=project,
            module_set=project.current_standard_module_set,
            start_date=date(2026, 1, 1),
        )
        self.assessment = Assessment.objects.create(
            name="考核资料清理测试",
            training_cycle=training_cycle,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 2),
        )

    def _pdf_upload(self, name: str) -> SimpleUploadedFile:
        return SimpleUploadedFile(name, b"%PDF-1.4\nassessment material", content_type="application/pdf")

    def _create_assessment_module(self, filename: str = "question.pdf") -> AssessmentModule:
        return AssessmentModule.objects.create(
            assessment=self.assessment,
            module=self.module,
            question_file=self._pdf_upload(filename),
        )

    def test_clearing_material_file_field_deletes_old_physical_file(self):
        assessment_module = self._create_assessment_module("clear-question.pdf")
        old_file_name = assessment_module.question_file.name
        storage = assessment_module.question_file.storage
        self.assertTrue(storage.exists(old_file_name))

        assessment_module.question_file = ""
        assessment_module.save()

        assessment_module.refresh_from_db()
        self.assertFalse(storage.exists(old_file_name))
        self.assertFalse(assessment_module.question_file.name)

    def test_replacing_material_file_deletes_old_physical_file(self):
        assessment_module = self._create_assessment_module("old-question.pdf")
        old_file_name = assessment_module.question_file.name
        storage = assessment_module.question_file.storage
        self.assertTrue(storage.exists(old_file_name))

        assessment_module.question_file = self._pdf_upload("new-question.pdf")
        assessment_module.save()

        assessment_module.refresh_from_db()
        self.assertFalse(storage.exists(old_file_name))
        self.assertTrue(assessment_module.question_file.storage.exists(assessment_module.question_file.name))

    def test_deleting_assessment_module_deletes_material_file(self):
        assessment_module = self._create_assessment_module("delete-question.pdf")
        file_name = assessment_module.question_file.name
        storage = assessment_module.question_file.storage
        self.assertTrue(storage.exists(file_name))

        assessment_module.delete()

        self.assertFalse(storage.exists(file_name))

    def test_deleting_assessment_attachment_deletes_physical_file(self):
        assessment_module = self._create_assessment_module("attachment-parent.pdf")
        attachment = AssessmentAttachment.objects.create(
            assessment_module=assessment_module,
            file=self._pdf_upload("attachment.pdf"),
            description="附件清理测试",
        )
        file_name = attachment.file.name
        storage = attachment.file.storage
        self.assertTrue(storage.exists(file_name))

        attachment.delete()

        self.assertFalse(storage.exists(file_name))
