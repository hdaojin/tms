from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from assessments.models import (
    Assessment,
    AssessmentDocument,
    AssessmentModule,
    AssessmentModuleCoach,
    AssessmentModuleDomain,
    AssessmentParticipant,
    AssessmentType,
    CompetitionRole,
)
from evidence.models import KnowledgeEvidence
from standards.models import SkillProject, TechnicalDomain, TechnicalDomainGroupScope
from core.bootstrap_engine import bootstrap_defaults as bootstrap_scoring_defaults
from .forms import ScoringImportForm, ScoringResultForm
from .models import (
    ScoringAspect,
    ScoringResult,
    ScoringResultImport,
    ScoringResultRevision,
    ScoringScheme,
    ScoringSchemeImport,
    ScoringSubCriterion,
)
from .parser import WorkbookParseError
from .selectors import module_scoring_summary, scoring_results_visible_to, scoring_schemes_in_scope_for
from .services import (
    confirm_scheme_import,
    parse_scheme_document,
    record_scoring_result,
    scheme_import_consistency_report,
)

User = get_user_model()


def get_mock_assessment_type():
    return AssessmentType.objects.get_or_create(
        code='mock',
        defaults={'name': '模拟赛', 'order': 40},
    )[0]


class ScoringEvidenceWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="coach")
        self.user.user_permissions.add(
            Permission.objects.get(content_type__app_label="scoring", codename="add_scoringscheme")
        )
        self.user = User.objects.get(pk=self.user.pk)
        project = SkillProject.objects.create(code="NS", name="网络系统管理")
        assessment = Assessment.objects.create(
            skill_project=project,
            assessment_type=get_mock_assessment_type(),
            name="模拟赛",
            code="MOCK",
            start_date=date(2026, 1, 1),
            created_by=self.user,
        )
        self.module = AssessmentModule.objects.create(assessment=assessment, code="A", name="模块 A")
        self.document = AssessmentDocument.objects.create(
            assessment=assessment,
            module=self.module,
            document_type=AssessmentDocument.DocumentType.MARKING_STANDARD,
            title="评分标准",
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
        imported = self.create_import(
            {
                "subcriteria": [
                    {
                        "code": "A1",
                        "name": "服务部署",
                        "aspects": [
                            {
                                "code": "A1.1",
                                "aspect_type": "M",
                                "description": "服务可用",
                                "max_mark": "2.00",
                                "source_row_number": 10,
                            }
                        ],
                    }
                ]
            }
        )
        first = confirm_scheme_import(imported, user=self.user)
        second = confirm_scheme_import(imported, user=self.user)
        self.assertEqual(first.pk, second.pk)

    def test_consistency_report_warns_for_unconfigured_module_total(self):
        imported = self.create_import(
            {"subcriteria": [{"code": "A1", "name": "服务部署", "aspects": [{"code": "A1.1", "max_mark": "2"}]}]}
        )

        report = scheme_import_consistency_report(imported)

        self.assertTrue(report["can_confirm"])
        self.assertEqual(report["checks"]["assessment_module_total"], "0.00")
        self.assertIn("尚未配置总分", report["warnings"][0])

    def test_confirm_blocks_configured_module_total_mismatch(self):
        self.module.total_mark = Decimal("10")
        self.module.save(update_fields=["total_mark"])
        imported = self.create_import(
            {"subcriteria": [{"code": "A1", "name": "服务部署", "aspects": [{"code": "A1.1", "max_mark": "2"}]}]}
        )

        with self.assertRaisesMessage(ValidationError, "评测模块配置总分 10.00"):
            confirm_scheme_import(imported, user=self.user)

        self.assertFalse(ScoringScheme.objects.exists())
        imported.refresh_from_db()
        self.assertEqual(imported.status, ScoringSchemeImport.Status.PARSED)

    def test_confirm_rechecks_module_total_changed_after_preview(self):
        imported = self.create_import(
            {"subcriteria": [{"code": "A1", "name": "服务部署", "aspects": [{"code": "A1.1", "max_mark": "2"}]}]}
        )
        self.assertTrue(scheme_import_consistency_report(imported)["can_confirm"])
        self.module.total_mark = Decimal("3")
        self.module.save(update_fields=["total_mark"])

        with self.assertRaisesMessage(ValidationError, "评测模块配置总分 3.00"):
            confirm_scheme_import(imported, user=self.user)

    def test_confirm_blocks_payload_aspect_total_mismatch(self):
        imported = self.create_import(
            {"subcriteria": [{"code": "A1", "name": "服务部署", "aspects": [{"code": "A1.1", "max_mark": "1.50"}]}]}
        )

        with self.assertRaisesMessage(ValidationError, "评分点分值合计 1.50"):
            confirm_scheme_import(imported, user=self.user)

    def test_preview_displays_consistency_errors_and_disables_confirmation(self):
        self.module.total_mark = Decimal("3")
        self.module.save(update_fields=["total_mark"])
        imported = self.create_import(
            {"subcriteria": [{"code": "A1", "name": "服务部署", "aspects": [{"code": "A1.1", "max_mark": "2"}]}]}
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("scoring:scheme_import_preview", args=[imported.pk]))

        self.assertContains(response, "评测模块配置总分 3.00")
        self.assertContains(response, "disabled")

    def test_marking_sheet_cannot_be_used_as_scoring_scheme_source(self):
        marking_sheet = AssessmentDocument.objects.create(
            assessment=self.module.assessment,
            module=self.module,
            document_type=AssessmentDocument.DocumentType.ATTACHMENT,
            title="评分表",
            file="marking-sheet.xlsx",
            original_filename="marking-sheet.xlsx",
            file_sha256="b" * 64,
            uploaded_by=self.user,
        )

        with self.assertRaisesMessage(ValidationError, "只能解析绑定评测模块的评分标准资料"):
            parse_scheme_document(marking_sheet, parser_config=None, user=self.user)
        with self.assertRaisesMessage(ValidationError, "评分方案来源资料必须是评分标准"):
            ScoringScheme.objects.create(
                assessment_module=self.module,
                source_document=marking_sheet,
                title="错误来源方案",
                module_code="A",
                module_name="模块 A",
            )

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


class ScoringResultModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="scorer")
        self.project = SkillProject.objects.create(code="SCORE", name="评分测试")
        self.assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name="评分测试",
            code="SCORE-ASSESSMENT",
            start_date=date(2026, 2, 1),
            created_by=self.user,
        )
        self.module = AssessmentModule.objects.create(assessment=self.assessment, code="A", name="模块 A")
        self.scheme = ScoringScheme.objects.create(
            assessment_module=self.module,
            title="评分方案",
            module_code="A",
            module_name="模块 A",
            total_mark=Decimal("10"),
        )
        subcriterion = ScoringSubCriterion.objects.create(scheme=self.scheme, code="A1", name="评分子项")
        self.aspect = ScoringAspect.objects.create(
            scheme=self.scheme,
            subcriterion=subcriterion,
            code="A1.1",
            aspect_type=ScoringAspect.AspectType.MEASUREMENT,
            description="评分点",
            max_mark=Decimal("10"),
            source_row_number=1,
        )
        self.competitor_role = CompetitionRole.objects.create(
            code="competitor-scoring-test",
            name="选手",
            category=CompetitionRole.Category.COMPETITOR,
        )
        self.expert_role = CompetitionRole.objects.create(
            code="expert-scoring-test",
            name="专家",
            category=CompetitionRole.Category.EXPERT,
        )
        self.participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            user=self.user,
            display_name="测试选手",
            role=self.competitor_role,
        )

    def test_result_directly_uses_competitor_assessment_participant(self):
        result = ScoringResult.objects.create(
            participant=self.participant,
            aspect=self.aspect,
            score_awarded=Decimal("8"),
            source=ScoringResult.Source.ONLINE,
            entered_by=self.user,
        )
        self.assertEqual(result.participant, self.participant)
        self.assertEqual(result.source, ScoringResult.Source.ONLINE)

    def test_result_rejects_non_competitor_and_cross_assessment_participant(self):
        expert = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            display_name="专家",
            role=self.expert_role,
        )
        with self.assertRaisesMessage(ValidationError, "只有选手类"):
            ScoringResult.objects.create(participant=expert, aspect=self.aspect, score_awarded=Decimal("8"))

        other_assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name="另一场",
            code="SCORE-OTHER",
            start_date=date(2026, 2, 2),
            created_by=self.user,
        )
        other_participant = AssessmentParticipant.objects.create(
            assessment=other_assessment,
            display_name="另一场选手",
            role=self.competitor_role,
        )
        with self.assertRaisesMessage(ValidationError, "必须属于评分方案对应"):
            ScoringResult.objects.create(
                participant=other_participant,
                aspect=self.aspect,
                score_awarded=Decimal("8"),
            )

    def test_result_enforces_score_and_confirmation_constraints(self):
        with self.assertRaisesMessage(ValidationError, "不能超过"):
            ScoringResult.objects.create(
                participant=self.participant,
                aspect=self.aspect,
                score_awarded=Decimal("11"),
            )
        with self.assertRaisesMessage(ValidationError, "必须同时填写"):
            ScoringResult.objects.create(
                participant=self.participant,
                aspect=self.aspect,
                score_awarded=Decimal("8"),
                confirmed_by=self.user,
            )

    def test_result_is_unique_per_participant_and_aspect(self):
        ScoringResult.objects.create(
            participant=self.participant,
            aspect=self.aspect,
            score_awarded=Decimal("8"),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ScoringResult.objects.bulk_create(
                [
                    ScoringResult(
                        participant=self.participant,
                        aspect=self.aspect,
                        score_awarded=Decimal("7"),
                    )
                ]
            )

    def test_revision_keeps_old_and_new_score(self):
        result = ScoringResult.objects.create(
            participant=self.participant,
            aspect=self.aspect,
            score_awarded=Decimal("8"),
        )
        revision = ScoringResultRevision.objects.create(
            scoring_result=result,
            old_score=Decimal("8"),
            new_score=Decimal("9"),
            changed_by=self.user,
            reason="复核",
        )
        self.assertEqual(revision.old_score, Decimal("8"))
        self.assertEqual(revision.new_score, Decimal("9"))


class OnlineScoringWorkflowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="online-owner")
        self.coach = User.objects.create_user(username="online-coach")
        self.read_only = User.objects.create_user(username="online-read-only")
        self.student = User.objects.create_user(username="online-student")
        self.split_scope = User.objects.create_user(username="online-split-scope")
        self.project = SkillProject.objects.create(code="ONLINE", name="在线评分")
        self.domain = TechnicalDomain.objects.create(skill_project=self.project, code="ONLINE-LINUX", name="Linux")
        self.other_domain = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="ONLINE-WINDOWS",
            name="Windows",
        )
        self.assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name="在线评分测试",
            code="ONLINE-ASSESSMENT",
            start_date=date(2026, 5, 1),
            created_by=self.owner,
        )
        self.module = self._module(self.assessment, "A", self.domain)
        self.other_module = self._module(self.assessment, "B", self.other_domain)
        self.scheme, self.aspect = self._scheme(self.module, "A")
        self.other_scheme, self.other_aspect = self._scheme(self.other_module, "B")
        competitor_role = CompetitionRole.objects.create(
            code="online-competitor",
            name="选手",
            category=CompetitionRole.Category.COMPETITOR,
        )
        self.participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            role=competitor_role,
            display_name="选手一",
        )
        self.other_participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            role=competitor_role,
            display_name="选手二",
        )
        self.coach = self._grant_group(
            self.coach,
            "在线评分教练",
            [
                "scoring.view_scoringscheme",
                "scoring.view_scoringresult",
                "scoring.view_all_scoringresult",
                "scoring.add_scoringresult",
                "scoring.change_scoringresult",
                "scoring.view_scoringresultrevision",
            ],
            [self.domain],
        )
        self.read_only = self._grant_group(
            self.read_only,
            "在线评分只读",
            [
                "scoring.view_scoringscheme",
                "scoring.view_scoringresult",
                "scoring.view_all_scoringresult",
            ],
            [self.domain],
        )
        self.student.user_permissions.add(
            Permission.objects.get(content_type__app_label="scoring", codename="view_scoringresult")
        )

    @staticmethod
    def _module(assessment, code, domain):
        module = AssessmentModule.objects.create(assessment=assessment, code=code, name=f"模块 {code}")
        AssessmentModuleDomain.objects.create(
            assessment_module=module,
            technical_domain=domain,
            role=AssessmentModuleDomain.Role.PRIMARY,
        )
        return module

    @staticmethod
    def _scheme(module, code):
        scheme = ScoringScheme.objects.create(
            assessment_module=module,
            title=f"{code} 评分方案",
            module_code=code,
            module_name=module.name,
            total_mark=Decimal("10"),
        )
        subcriterion = ScoringSubCriterion.objects.create(scheme=scheme, code=f"{code}1", name="评分子项")
        aspect = ScoringAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion,
            code=f"{code}1.1",
            aspect_type=ScoringAspect.AspectType.MEASUREMENT,
            description="服务可用",
            max_mark=Decimal("10"),
            source_row_number=1,
        )
        return scheme, aspect

    @staticmethod
    def _grant_group(user, name, permission_names, domains):
        group = Group.objects.create(name=name)
        group.permissions.add(
            *[
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
                for app_label, codename in (item.split(".", maxsplit=1) for item in permission_names)
            ]
        )
        for domain in domains:
            TechnicalDomainGroupScope.objects.create(group=group, technical_domain=domain)
        user.groups.add(group)
        return User.objects.get(pk=user.pk)

    def test_service_creates_confirms_and_aggregates_online_score(self):
        result = record_scoring_result(
            participant=self.participant,
            aspect=self.aspect,
            score_awarded=Decimal("8"),
            user=self.coach,
            confirm=True,
            evidence="服务检查通过",
        )

        self.assertEqual(result.source, ScoringResult.Source.ONLINE)
        self.assertEqual(result.entered_by, self.coach)
        self.assertEqual(result.updated_by, self.coach)
        self.assertEqual(result.confirmed_by, self.coach)
        self.assertIsNotNone(result.confirmed_at)
        self.assertFalse(result.revisions.exists())
        summary = module_scoring_summary(self.module, self.scheme)
        self.assertEqual(summary["expected_count"], 2)
        self.assertEqual(summary["scored_count"], 1)
        self.assertEqual(summary["confirmed_count"], 1)
        self.assertEqual(summary["completion_percent"], Decimal("50.0"))
        self.assertEqual(summary["score_rate"], Decimal("40.0"))

    def test_service_update_records_revision_and_requires_reconfirmation(self):
        original = record_scoring_result(
            participant=self.participant,
            aspect=self.aspect,
            score_awarded=Decimal("8"),
            user=self.coach,
            confirm=True,
        )

        updated = record_scoring_result(
            participant=self.participant,
            aspect=self.aspect,
            score_awarded=Decimal("7"),
            user=self.coach,
            reason="复核评分表",
        )

        self.assertEqual(updated.pk, original.pk)
        self.assertIsNone(updated.confirmed_by)
        self.assertIsNone(updated.confirmed_at)
        revision = updated.revisions.get()
        self.assertEqual(revision.old_score, Decimal("8"))
        self.assertEqual(revision.new_score, Decimal("7"))
        self.assertEqual(revision.changed_by, self.coach)
        self.assertEqual(revision.reason, "复核评分表")

        record_scoring_result(
            participant=self.participant,
            aspect=self.aspect,
            score_awarded=Decimal("7"),
            user=self.coach,
        )
        self.assertEqual(updated.revisions.count(), 1)

    def test_external_sources_write_the_same_scoring_result(self):
        imported = record_scoring_result(
            participant=self.participant,
            aspect=self.aspect,
            score_awarded=Decimal("6"),
            user=self.coach,
            source=ScoringResult.Source.EXCEL_IMPORT,
            raw_payload={"row": 12},
        )
        updated = record_scoring_result(
            participant=self.participant,
            aspect=self.aspect,
            score_awarded=Decimal("6"),
            user=self.coach,
            source=ScoringResult.Source.CMP_IMPORT,
            raw_payload={"result_id": "CMP-1"},
        )

        self.assertEqual(updated.pk, imported.pk)
        self.assertEqual(ScoringResult.objects.count(), 1)
        self.assertEqual(updated.source, ScoringResult.Source.CMP_IMPORT)
        self.assertEqual(updated.raw_payload, {"result_id": "CMP-1"})

    def test_service_enforces_score_and_same_group_domain_scope(self):
        with self.assertRaisesMessage(ValidationError, "不能超过评分点分值"):
            record_scoring_result(
                participant=self.participant,
                aspect=self.aspect,
                score_awarded=Decimal("11"),
                user=self.coach,
            )

        self.split_scope.user_permissions.add(
            Permission.objects.get(content_type__app_label="scoring", codename="add_scoringresult")
        )
        scope_group = Group.objects.create(name="在线评分仅 Scope")
        TechnicalDomainGroupScope.objects.create(group=scope_group, technical_domain=self.domain)
        self.split_scope.groups.add(scope_group)
        self.split_scope = User.objects.get(pk=self.split_scope.pk)
        with self.assertRaises(PermissionDenied):
            record_scoring_result(
                participant=self.participant,
                aspect=self.aspect,
                score_awarded=Decimal("8"),
                user=self.split_scope,
            )

    def test_workspace_supports_both_views_and_htmx_submission(self):
        self.client.force_login(self.coach)
        workspace_url = reverse("scoring:online_scoring", args=[self.module.pk])
        response = self.client.get(workspace_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "按选手")
        self.assertContains(response, "选手一")

        response = self.client.get(workspace_url, {"perspective": "aspect", "aspect": self.aspect.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "按评分点")
        self.assertContains(response, "选手二")

        response = self.client.post(
            reverse(
                "scoring:online_scoring_entry",
                args=[self.module.pk, self.participant.pk, self.aspect.pk],
            ),
            {"perspective": "participant", "score_awarded": "9.00", "confirm": "on"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="online-scoring-workspace"')
        self.assertContains(response, "已保存")
        result = ScoringResult.objects.get(participant=self.participant, aspect=self.aspect)
        self.assertEqual(result.score_awarded, Decimal("9.00"))
        self.assertEqual(result.source, ScoringResult.Source.ONLINE)

    def test_workspace_hides_other_domains_and_is_read_only_without_change_permission(self):
        self.client.force_login(self.coach)
        self.assertEqual(
            self.client.get(reverse("scoring:online_scoring", args=[self.other_module.pk])).status_code,
            404,
        )

        self.client.force_login(self.read_only)
        response = self.client.get(reverse("scoring:online_scoring", args=[self.module.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "仅查看")
        response = self.client.post(
            reverse(
                "scoring:online_scoring_entry",
                args=[self.module.pk, self.participant.pk, self.aspect.pk],
            ),
            {"perspective": "participant", "score_awarded": "9.00"},
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.student)
        self.assertEqual(
            self.client.get(reverse("scoring:online_scoring", args=[self.module.pk])).status_code,
            403,
        )


class ScoringPermissionBoundaryTests(TestCase):
    def setUp(self):
        bootstrap_scoring_defaults()
        self.owner = User.objects.create_user(username="scoring-permission-owner")
        self.other_owner = User.objects.create_user(username="scoring-permission-other-owner")
        self.linux_coach = User.objects.create_user(username="scoring-linux-coach")
        self.project_manager = User.objects.create_user(username="scoring-project-manager")
        self.split_scope_user = User.objects.create_user(username="scoring-split-scope")
        self.project = SkillProject.objects.create(code="SCORING-PERM", name="评分权限项目")
        self.linux = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="SCORING-LINUX",
            name="Linux",
        )
        self.windows = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="SCORING-WINDOWS",
            name="Windows",
        )
        self.linux_assessment = self._assessment("SCORING-LINUX", self.owner)
        self.windows_assessment = self._assessment("SCORING-WINDOWS", self.other_owner)
        self.linux_module = self._module(self.linux_assessment, "L", self.linux)
        self.windows_module = self._module(self.windows_assessment, "W", self.windows)
        self.cross_module = AssessmentModule.objects.create(
            assessment=self.linux_assessment,
            code="CROSS",
            name="跨领域模块",
        )
        AssessmentModuleDomain.objects.create(
            assessment_module=self.cross_module,
            technical_domain=self.linux,
            role=AssessmentModuleDomain.Role.PRIMARY,
        )
        AssessmentModuleDomain.objects.create(
            assessment_module=self.cross_module,
            technical_domain=self.windows,
        )
        self.linux_scheme, self.linux_aspect = self._scheme(self.linux_module, "L")
        self.windows_scheme, self.windows_aspect = self._scheme(self.windows_module, "W")
        self.cross_scheme, self.cross_aspect = self._scheme(self.cross_module, "C")
        self.linux_document = self._document(self.linux_module, "3")
        self.windows_document = self._document(self.windows_module, "4")
        self.cross_document = self._document(self.cross_module, "5")
        self.linux_import = self._scheme_import(self.linux_module, self.linux_document, "L")
        self.windows_import = self._scheme_import(self.windows_module, self.windows_document, "W")
        competitor_role = CompetitionRole.objects.create(
            code="scoring-permission-competitor",
            name="选手",
            category=CompetitionRole.Category.COMPETITOR,
        )
        linux_participant = AssessmentParticipant.objects.create(
            assessment=self.linux_assessment,
            role=competitor_role,
            display_name="Linux 选手",
        )
        windows_participant = AssessmentParticipant.objects.create(
            assessment=self.windows_assessment,
            role=competitor_role,
            display_name="Windows 选手",
        )
        self.linux_result = ScoringResult.objects.create(
            participant=linux_participant,
            aspect=self.linux_aspect,
            score_awarded=Decimal("8"),
        )
        self.windows_result = ScoringResult.objects.create(
            participant=windows_participant,
            aspect=self.windows_aspect,
            score_awarded=Decimal("7"),
        )
        self.linux_coach = self._grant_group(
            self.linux_coach,
            "Linux 评分权限",
            [
                "scoring.view_scoringscheme",
                "scoring.add_scoringscheme",
                "scoring.view_scoringresult",
                "scoring.view_all_scoringresult",
                "scoring.add_scoringresult",
            ],
            [self.linux],
        )

    def _assessment(self, code, owner):
        return Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name=code,
            code=code,
            start_date=date(2026, 4, 1),
            created_by=owner,
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

    @staticmethod
    def _scheme(module, code):
        scheme = ScoringScheme.objects.create(
            assessment_module=module,
            title=f"{code} 方案",
            module_code=module.code,
            module_name=module.name,
            total_mark=Decimal("10"),
        )
        subcriterion = ScoringSubCriterion.objects.create(scheme=scheme, code=f"{code}1", name="评分子项")
        aspect = ScoringAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion,
            code=f"{code}1.1",
            aspect_type=ScoringAspect.AspectType.MEASUREMENT,
            description="评分点",
            max_mark=Decimal("10"),
            source_row_number=1,
        )
        return scheme, aspect

    def _document(self, module, hash_character):
        return AssessmentDocument.objects.create(
            assessment=module.assessment,
            module=module,
            document_type=AssessmentDocument.DocumentType.MARKING_STANDARD,
            title=f"{module.code} 评分标准",
            file=f"{module.code}.xlsx",
            original_filename=f"{module.code}.xlsx",
            file_sha256=hash_character * 64,
            uploaded_by=self.owner,
        )

    @staticmethod
    def _scheme_import(module, document, code):
        return ScoringSchemeImport.objects.create(
            assessment_module=module,
            source_document=document,
            parser_key="cmp_single_module_v1",
            parser_display_name="CMP",
            title=f"{code} 导入",
            module_code=module.code,
            module_name=module.name,
            module_mark=Decimal("10"),
            total_mark=Decimal("10"),
            parsed_payload={"subcriteria": []},
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

    def test_scheme_and_result_scope_use_same_group_permission_and_domain(self):
        self.assertIn(self.linux_scheme, scoring_schemes_in_scope_for(self.linux_coach))
        self.assertNotIn(self.windows_scheme, scoring_schemes_in_scope_for(self.linux_coach))
        self.assertNotIn(self.cross_scheme, scoring_schemes_in_scope_for(self.linux_coach))
        self.assertIn(self.linux_result, scoring_results_visible_to(self.linux_coach))
        self.assertNotIn(self.windows_result, scoring_results_visible_to(self.linux_coach))

        AssessmentModuleCoach.objects.create(assessment_module=self.cross_module, user=self.linux_coach)
        self.assertIn(self.cross_scheme, scoring_schemes_in_scope_for(self.linux_coach))

        self.split_scope_user.user_permissions.add(*self._permissions(["scoring.view_scoringscheme"]))
        scope_only_group = Group.objects.create(name="评分仅 Linux Scope")
        TechnicalDomainGroupScope.objects.create(group=scope_only_group, technical_domain=self.linux)
        self.split_scope_user.groups.add(scope_only_group)
        self.split_scope_user = User.objects.get(pk=self.split_scope_user.pk)
        self.assertNotIn(self.linux_scheme, scoring_schemes_in_scope_for(self.split_scope_user))

    def test_scheme_detail_and_import_preview_return_404_outside_scope(self):
        self.client.force_login(self.linux_coach)
        self.assertEqual(
            self.client.get(reverse("scoring:scheme_detail", args=[self.linux_scheme.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("scoring:scheme_detail", args=[self.windows_scheme.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("scoring:scheme_import_preview", args=[self.linux_import.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("scoring:scheme_import_preview", args=[self.windows_import.pk])).status_code,
            404,
        )

    def test_import_and_result_forms_only_offer_in_scope_objects(self):
        marking_sheet = AssessmentDocument.objects.create(
            assessment=self.linux_module.assessment,
            module=self.linux_module,
            document_type=AssessmentDocument.DocumentType.ATTACHMENT,
            title="Linux 评分表",
            file="linux-marking-sheet.xlsx",
            original_filename="linux-marking-sheet.xlsx",
            file_sha256="d" * 64,
            uploaded_by=self.owner,
        )
        import_form = ScoringImportForm(user=self.linux_coach)
        self.assertIn(self.linux_document, import_form.fields["source_document"].queryset)
        self.assertNotIn(marking_sheet, import_form.fields["source_document"].queryset)
        self.assertNotIn(self.windows_document, import_form.fields["source_document"].queryset)
        self.assertNotIn(self.cross_document, import_form.fields["source_document"].queryset)
        contextual_import_form = ScoringImportForm(
            user=self.linux_coach,
            module_id=self.linux_module.pk,
        )
        self.assertEqual(
            list(contextual_import_form.fields["source_document"].queryset),
            [self.linux_document],
        )

        result_form = ScoringResultForm(user=self.linux_coach)
        self.assertIn(self.linux_aspect, result_form.fields["aspect"].queryset)
        self.assertNotIn(self.windows_aspect, result_form.fields["aspect"].queryset)
        self.assertNotIn(self.cross_aspect, result_form.fields["aspect"].queryset)

    def test_import_parse_error_is_attached_to_source_document(self):
        self.client.force_login(self.linux_coach)
        parser_config = ScoringImportForm(user=self.linux_coach).fields["parser_config"].queryset.get(is_default=True)

        with patch(
            "scoring.views.parse_scheme_document",
            side_effect=WorkbookParseError("评分标准格式错误。"),
        ):
            response = self.client.post(
                reverse("scoring:scheme_import"),
                {
                    "source_document": self.linux_document.pk,
                    "parser_config": parser_config.pk,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "source_document", "评分标准格式错误。")

    def test_service_rejects_import_confirmation_outside_scope(self):
        self.split_scope_user.user_permissions.add(*self._permissions(["scoring.add_scoringscheme"]))
        scope_only_group = Group.objects.create(name="导入仅 Windows Scope")
        TechnicalDomainGroupScope.objects.create(group=scope_only_group, technical_domain=self.windows)
        self.split_scope_user.groups.add(scope_only_group)
        self.split_scope_user = User.objects.get(pk=self.split_scope_user.pk)

        with self.assertRaises(PermissionDenied):
            confirm_scheme_import(self.linux_import, user=self.split_scope_user)
        self.linux_import.refresh_from_db()
        self.assertEqual(self.linux_import.status, ScoringSchemeImport.Status.PARSED)

    def test_project_wide_assessment_permission_expands_scoring_scope(self):
        self.project_manager = self._grant_group(
            self.project_manager,
            "评分项目负责人",
            [
                "assessments.view_all_assessment",
                "assessments.change_all_assessment",
                "scoring.view_scoringscheme",
                "scoring.add_scoringscheme",
            ],
        )
        self.assertIn(self.windows_scheme, scoring_schemes_in_scope_for(self.project_manager))
        import_form = ScoringImportForm(user=self.project_manager)
        self.assertIn(self.windows_document, import_form.fields["source_document"].queryset)
