from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from assessments.models import Assessment, AssessmentDocument, AssessmentModule
from evidence.models import KnowledgeEvidence
from standards.models import SkillProject
from .models import ScoringResultImport, ScoringScheme, ScoringSchemeImport
from .services import confirm_scheme_import

User = get_user_model()


class ScoringEvidenceWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="coach")
        project = SkillProject.objects.create(code="NS", name="网络系统管理")
        assessment = Assessment.objects.create(
            skill_project=project,
            assessment_type=Assessment.Type.MOCK,
            name="模拟赛",
            code="MOCK",
            start_date=date(2026, 1, 1),
            created_by=self.user,
        )
        self.module = AssessmentModule.objects.create(assessment=assessment, code="A", name="模块 A")
        self.document = AssessmentDocument.objects.create(
            assessment=assessment,
            module=self.module,
            document_type=AssessmentDocument.DocumentType.MARKING_SCHEME,
            title="评分表",
            file="placeholder.xlsx",
            original_filename="scheme.xlsx",
            file_sha256="a" * 64,
            uploaded_by=self.user,
        )

    def create_import(self, payload):
        return ScoringSchemeImport.objects.create(
            assessment_module=self.module,
            source_document=self.document,
            parser_key="cmp_single_module_v1",
            parser_display_name="CMP",
            title="评分方案",
            module_code="A",
            module_name="模块 A",
            module_mark=Decimal("2"),
            total_mark=Decimal("2"),
            parsed_payload=payload,
            imported_by=self.user,
        )

    def test_confirm_import_creates_approved_evidence_for_every_aspect(self):
        payload = {
            "subcriteria": [
                {
                    "code": "A1",
                    "name": "服务部署",
                    "order": 1,
                    "aspects": [
                        {
                            "code": "A1.1",
                            "aspect_type": "M",
                            "description": "服务可用",
                            "requirement": "检查成功",
                            "max_mark": "2.00",
                            "source_row_number": 10,
                            "order": 1,
                        }
                    ],
                }
            ]
        }
        scheme = confirm_scheme_import(self.create_import(payload), user=self.user)
        evidence = KnowledgeEvidence.objects.get(scoring_aspect__scheme=scheme)
        self.assertEqual(evidence.review_status, KnowledgeEvidence.ReviewStatus.APPROVED)
        self.assertEqual(evidence.extraction_source, KnowledgeEvidence.ExtractionSource.PARSER)

    def test_confirm_is_idempotent(self):
        imported = self.create_import({"subcriteria": []})
        first = confirm_scheme_import(imported, user=self.user)
        second = confirm_scheme_import(imported, user=self.user)
        self.assertEqual(first.pk, second.pk)

    def test_result_import_accepts_only_result_file_from_same_module(self):
        scheme = ScoringScheme.objects.create(
            assessment_module=self.module,
            title="评分方案",
            module_code="A",
            module_name="模块 A",
        )
        with self.assertRaisesMessage(ValidationError, "必须是成绩或结果文件"):
            ScoringResultImport.objects.create(scheme=scheme, source_document=self.document, imported_by=self.user)

        result_document = AssessmentDocument.objects.create(
            assessment=self.module.assessment,
            module=self.module,
            document_type=AssessmentDocument.DocumentType.RESULT_FILE,
            title="成绩结果",
            file="result.zip",
            original_filename="result.zip",
            file_sha256="b" * 64,
            uploaded_by=self.user,
        )
        imported = ScoringResultImport.objects.create(
            scheme=scheme,
            source_document=result_document,
            imported_by=self.user,
        )
        self.assertEqual(imported.source_document, result_document)
