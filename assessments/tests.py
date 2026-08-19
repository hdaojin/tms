from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from standards.models import SkillProject, TechnicalDomain
from .models import Assessment, AssessmentDocument, AssessmentModule, AssessmentModuleDomain

User = get_user_model()


class AssessmentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner")
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=Assessment.Type.MOCK,
            name="模拟赛",
            code="MOCK",
            start_date=date(2026, 1, 1),
            created_by=self.user,
        )

    def test_end_date_cannot_precede_start_date(self):
        self.assessment.end_date = date(2025, 12, 31)
        with self.assertRaises(ValidationError):
            self.assessment.save()

    def test_module_domain_must_belong_to_assessment_project(self):
        module = AssessmentModule.objects.create(assessment=self.assessment, code="A", name="模块 A")
        other = SkillProject.objects.create(code="OTHER", name="其他")
        domain = TechnicalDomain.objects.create(skill_project=other, code="OTHER", name="其他")
        with self.assertRaises(ValidationError):
            AssessmentModuleDomain.objects.create(assessment_module=module, technical_domain=domain)

    def test_document_module_must_belong_to_same_assessment(self):
        other_assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=Assessment.Type.MOCK,
            name="另一场",
            code="OTHER",
            start_date=date(2026, 2, 1),
            created_by=self.user,
        )
        other_module = AssessmentModule.objects.create(assessment=other_assessment, code="A", name="模块 A")
        document = AssessmentDocument(
            assessment=self.assessment,
            module=other_module,
            document_type=AssessmentDocument.DocumentType.TEST_PROJECT,
            title="试题",
            file="test.pdf",
            original_filename="test.pdf",
            file_sha256="c" * 64,
            uploaded_by=self.user,
        )
        with self.assertRaises(ValidationError):
            document.save()

    def test_exact_document_duplicate_is_rejected_but_different_hash_version_is_allowed(self):
        module = AssessmentModule.objects.create(assessment=self.assessment, code="A", name="模块 A")
        values = {
            "assessment": self.assessment,
            "module": module,
            "document_type": AssessmentDocument.DocumentType.TEST_PROJECT,
            "title": "试题",
            "original_filename": "test.pdf",
            "uploaded_by": self.user,
        }
        AssessmentDocument.objects.create(file="first.pdf", file_sha256="a" * 64, version="V1", **values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssessmentDocument.objects.create(file="duplicate.pdf", file_sha256="a" * 64, version="V2", **values)
        self.assertIsNotNone(
            AssessmentDocument.objects.create(file="second.pdf", file_sha256="b" * 64, version="V2", **values).pk
        )
