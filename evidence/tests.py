from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from assessments.models import (
    Assessment,
    AssessmentModule,
    AssessmentModuleCoach,
    AssessmentModuleDomain,
    AssessmentParticipant,
    AssessmentType,
    CompetitionRole,
)
from scoring.models import ScoringAspect, ScoringResult, ScoringScheme, ScoringSubCriterion
from standards.models import Skill, SkillProject, TechnicalDomain, TechnicalDomainGroupScope
from standards.selectors import assessment_skill_performance, skill_assessment_performance
from .models import EvidenceSkillMap, KnowledgeEvidence
from .forms import KnowledgeEvidenceForm
from .views import manageable_evidences_for, visible_evidences_for

User = get_user_model()


def get_mock_assessment_type():
    return AssessmentType.objects.get_or_create(
        code='mock',
        defaults={'name': '模拟赛', 'order': 40},
    )[0]


class EvidenceMappingAndPerformanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="coach")
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.domain = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.skill = Skill.objects.create(skill_project=self.project, primary_domain=self.domain, name="Linux")
        self.assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name="模拟赛",
            code="MOCK",
            start_date=date(2026, 1, 1),
            created_by=self.user,
        )
        self.module = AssessmentModule.objects.create(assessment=self.assessment, code="A", name="模块 A")
        self.competitor_role = CompetitionRole.objects.create(
            code="competitor-evidence-test",
            name="选手",
            category=CompetitionRole.Category.COMPETITOR,
        )
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
        second = Skill.objects.create(skill_project=self.project, primary_domain=self.domain, name="Linux 2")
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
        participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            external_code="P1",
            display_name="选手",
            role=self.competitor_role,
        )
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

    def test_performance_explains_losses_and_respects_supplied_scope(self):
        scheme = ScoringScheme.objects.create(
            assessment_module=self.module,
            title="得失分方案",
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
            description="服务可用",
            max_mark=Decimal("10"),
            source_row_number=1,
        )
        self.evidence.scoring_aspect = aspect
        self.evidence.source_type = KnowledgeEvidence.SourceType.SCORING_ASPECT
        self.evidence.save()
        mapping = EvidenceSkillMap.objects.create(
            evidence=self.evidence,
            skill=self.skill,
            weight=Decimal("0.5"),
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        participant_one = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            external_code="P1",
            display_name="选手一",
            role=self.competitor_role,
        )
        participant_two = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            external_code="P2",
            display_name="选手二",
            role=self.competitor_role,
        )
        result_one = ScoringResult.objects.create(
            participant=participant_one,
            aspect=aspect,
            score_awarded=Decimal("8"),
        )
        ScoringResult.objects.create(
            participant=participant_two,
            aspect=aspect,
            score_awarded=Decimal("5"),
        )

        performance = skill_assessment_performance(self.skill)
        self.assertEqual(performance["awarded_mark"], Decimal("6.5"))
        self.assertEqual(performance["mapped_max_mark"], Decimal("10"))
        self.assertEqual(performance["lost_mark"], Decimal("3.5"))
        self.assertEqual(performance["score_rate"], Decimal("65.0"))
        self.assertEqual(performance["repeated_losses"][0]["result_count"], 2)
        self.assertEqual(performance["repeated_losses"][0]["lost_mark"], Decimal("3.5"))

        scoped_results = ScoringResult.objects.filter(pk=result_one.pk)
        scoped_evidences = KnowledgeEvidence.objects.filter(pk=self.evidence.pk)
        scoped = skill_assessment_performance(
            self.skill,
            results=scoped_results,
            evidences=scoped_evidences,
        )
        self.assertEqual(scoped["awarded_mark"], Decimal("4"))
        self.assertEqual(scoped["lost_mark"], Decimal("1"))
        self.assertEqual(scoped["repeated_losses"], [])

        assessment_rows = assessment_skill_performance(
            self.assessment,
            modules=[self.module],
            results=ScoringResult.objects.all(),
            evidences=scoped_evidences,
        )
        self.assertEqual(assessment_rows[0]["skill_id"], mapping.skill_id)
        self.assertEqual(assessment_rows[0]["awarded_mark"], Decimal("6.5"))
        self.assertEqual(assessment_rows[0]["lost_mark"], Decimal("3.5"))


class EvidencePermissionBoundaryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="evidence-permission-owner")
        self.linux_coach = User.objects.create_user(username="evidence-linux-coach")
        self.split_scope_user = User.objects.create_user(username="evidence-split-scope")
        self.project = SkillProject.objects.create(code="EVIDENCE-PERM", name="证据权限项目")
        self.linux = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="EVIDENCE-LINUX",
            name="Linux",
        )
        self.windows = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="EVIDENCE-WINDOWS",
            name="Windows",
        )
        assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name="证据权限评测",
            code="EVIDENCE-PERM-ASSESSMENT",
            start_date=date(2026, 5, 1),
            created_by=self.owner,
        )
        self.linux_module = self._module(assessment, "L", self.linux)
        self.windows_module = self._module(assessment, "W", self.windows)
        self.cross_module = AssessmentModule.objects.create(assessment=assessment, code="C", name="跨领域")
        AssessmentModuleDomain.objects.create(
            assessment_module=self.cross_module,
            technical_domain=self.linux,
            role=AssessmentModuleDomain.Role.PRIMARY,
        )
        AssessmentModuleDomain.objects.create(
            assessment_module=self.cross_module,
            technical_domain=self.windows,
        )
        self.linux_evidence = self._evidence(self.linux_module, "Linux 证据")
        self.windows_evidence = self._evidence(self.windows_module, "Windows 证据")
        self.cross_evidence = self._evidence(self.cross_module, "跨领域证据")
        self.linux_coach = self._grant_group(
            self.linux_coach,
            "Linux 证据权限",
            [
                "evidence.view_knowledgeevidence",
                "evidence.add_knowledgeevidence",
                "evidence.change_knowledgeevidence",
            ],
            [self.linux],
        )

    @staticmethod
    def _module(assessment, code, domain):
        module = AssessmentModule.objects.create(assessment=assessment, code=code, name=code)
        AssessmentModuleDomain.objects.create(
            assessment_module=module,
            technical_domain=domain,
            role=AssessmentModuleDomain.Role.PRIMARY,
        )
        return module

    def _evidence(self, module, title):
        return KnowledgeEvidence.objects.create(
            skill_project=self.project,
            assessment_module=module,
            source_type=KnowledgeEvidence.SourceType.MANUAL,
            title=title,
            created_by=self.owner,
        )

    @staticmethod
    def _permissions(permission_names):
        permissions = []
        for permission_name in permission_names:
            app_label, codename = permission_name.split(".", maxsplit=1)
            permissions.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
        return permissions

    def _grant_group(self, user, name, permission_names, domains=()):
        group = Group.objects.create(name=name)
        group.permissions.add(*self._permissions(permission_names))
        for domain in domains:
            TechnicalDomainGroupScope.objects.create(group=group, technical_domain=domain)
        user.groups.add(group)
        return User.objects.get(pk=user.pk)

    def test_evidence_scope_uses_evidence_permission_from_same_group(self):
        self.assertIn(self.linux_evidence, visible_evidences_for(self.linux_coach))
        self.assertNotIn(self.windows_evidence, visible_evidences_for(self.linux_coach))
        self.assertNotIn(self.cross_evidence, visible_evidences_for(self.linux_coach))
        self.assertIn(self.linux_evidence, manageable_evidences_for(self.linux_coach))

        AssessmentModuleCoach.objects.create(assessment_module=self.cross_module, user=self.linux_coach)
        self.assertIn(self.cross_evidence, visible_evidences_for(self.linux_coach))

        self.split_scope_user.user_permissions.add(*self._permissions(["evidence.view_knowledgeevidence"]))
        scope_only_group = Group.objects.create(name="证据仅 Linux Scope")
        TechnicalDomainGroupScope.objects.create(group=scope_only_group, technical_domain=self.linux)
        self.split_scope_user.groups.add(scope_only_group)
        self.split_scope_user = User.objects.get(pk=self.split_scope_user.pk)
        self.assertNotIn(self.linux_evidence, visible_evidences_for(self.split_scope_user))

    def test_evidence_detail_and_form_are_scoped(self):
        self.client.force_login(self.linux_coach)
        self.assertEqual(
            self.client.get(reverse("evidence:evidence_detail", args=[self.linux_evidence.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("evidence:evidence_detail", args=[self.windows_evidence.pk])).status_code,
            404,
        )
        form = KnowledgeEvidenceForm(user=self.linux_coach)
        self.assertIn(self.linux_module, form.fields["assessment_module"].queryset)
        self.assertNotIn(self.windows_module, form.fields["assessment_module"].queryset)
        self.assertNotIn(self.cross_module, form.fields["assessment_module"].queryset)
