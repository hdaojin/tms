from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from assessments.models import Assessment, AssessmentModule
from scoring.models import ScoringAspect, ScoringParticipant, ScoringResult, ScoringScheme, ScoringSubCriterion
from standards.models import Skill, SkillProject, TechnicalDomain
from standards.selectors import skill_assessment_performance
from .models import EvidenceSkillMap, KnowledgeEvidence

User = get_user_model()


class EvidenceMappingAndPerformanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="coach")
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.domain = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.skill = Skill.objects.create(
            skill_project=self.project, primary_domain=self.domain, name="Linux"
        )
        self.assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=Assessment.Type.MOCK,
            name="模拟赛",
            code="MOCK",
            start_date=date(2026, 1, 1),
            created_by=self.user,
        )
        self.module = AssessmentModule.objects.create(assessment=self.assessment, code="A", name="模块 A")
        self.evidence = KnowledgeEvidence.objects.create(
            skill_project=self.project,
            assessment_module=self.module,
            source_type=KnowledgeEvidence.SourceType.MANUAL,
            title="证据",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
            created_by=self.user,
        )

    def test_approved_mapping_weights_cannot_exceed_one(self):
        EvidenceSkillMap.objects.create(
            evidence=self.evidence,
            skill=self.skill,
            weight=Decimal("0.7"),
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        second = Skill.objects.create(
            skill_project=self.project, primary_domain=self.domain, name="Linux 2"
        )
        with self.assertRaises(ValidationError):
            EvidenceSkillMap.objects.create(
                evidence=self.evidence,
                skill=second,
                weight=Decimal("0.4"),
                review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
            )

    def test_mapping_correction_recalculates_performance_without_snapshot(self):
        scheme = ScoringScheme.objects.create(
            assessment_module=self.module,
            title="方案",
            module_code="A",
            module_name="模块 A",
            total_mark=Decimal("10"),
            imported_by=self.user,
        )
        subcriterion = ScoringSubCriterion.objects.create(scheme=scheme, code="A1", name="子项")
        aspect = ScoringAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion,
            code="A1.1",
            aspect_type=ScoringAspect.AspectType.MEASUREMENT,
            description="评分点",
            max_mark=Decimal("10"),
            source_row_number=1,
        )
        self.evidence.scoring_aspect = aspect
        self.evidence.source_type = KnowledgeEvidence.SourceType.SCORING_ASPECT
        self.evidence.save()
        participant = ScoringParticipant.objects.create(scheme=scheme, external_identifier="P1", display_name="选手")
        ScoringResult.objects.create(participant=participant, aspect=aspect, score_awarded=Decimal("8"))
        mapping = EvidenceSkillMap.objects.create(
            evidence=self.evidence,
            skill=self.skill,
            weight=Decimal("0.5"),
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        first = skill_assessment_performance(self.skill)
        mapping.weight = Decimal("0.25")
        mapping.save()
        second = skill_assessment_performance(self.skill)
        self.assertEqual(first["awarded_mark"], Decimal("4"))
        self.assertEqual(second["awarded_mark"], Decimal("2"))
