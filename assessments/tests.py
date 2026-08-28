from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from evidence.models import EvidenceSkillMap, KnowledgeEvidence
from scoring.models import ScoringAspect, ScoringResult, ScoringScheme, ScoringSubCriterion
from standards.models import Skill, SkillProject, TechnicalDomain, TechnicalDomainGroupScope
from .forms import AssessmentDocumentForm, AssessmentForm, AssessmentParticipantForm, AssessmentUpdateForm
from .models import (
    Assessment,
    AssessmentAward,
    AssessmentDocument,
    AssessmentFinalResult,
    AssessmentFinalScore,
    AssessmentModule,
    AssessmentModuleCoach,
    AssessmentModuleDomain,
    AssessmentParticipant,
    AssessmentResultAward,
    AssessmentType,
    CompetitionPerson,
    CompetitionRole,
)
from .selectors import (
    calculated_final_result_preview,
    manageable_assessment_modules_for,
    manageable_assessments_for,
    visible_assessment_modules_for,
    visible_assessment_participants_for,
    visible_assessments_for,
    visible_documents_for,
    visible_final_results_for,
)
from .services import (
    confirm_final_result,
    create_assessment_award,
    generate_final_results,
    publish_final_results,
    transition_assessment,
    update_final_result_details,
)
from .views import AssessmentDocumentCreateView

User = get_user_model()


def get_mock_assessment_type():
    return AssessmentType.objects.get_or_create(
        code='mock',
        defaults={'name': '模拟赛', 'order': 40},
    )[0]


class AssessmentCatalogFormTests(TestCase):
    def setUp(self):
        self.active_type = AssessmentType.objects.create(
            code='active-type',
            name='启用类型',
        )
        self.inactive_type = AssessmentType.objects.create(
            code='inactive-type',
            name='停用类型',
            is_active=False,
        )

    def test_create_excludes_inactive_type_but_edit_keeps_historical_value(self):
        create_form = AssessmentForm()
        self.assertIn(self.active_type, create_form.fields['assessment_type'].queryset)
        self.assertNotIn(self.inactive_type, create_form.fields['assessment_type'].queryset)

        assessment = Assessment.objects.create(
            skill_project=SkillProject.objects.create(code='CATALOG', name='目录测试'),
            assessment_type=self.inactive_type,
            name='历史考核',
            code='CATALOG-HISTORY',
            start_date=date(2026, 8, 24),
        )
        edit_form = AssessmentForm(instance=assessment)
        self.assertIn(self.inactive_type, edit_form.fields['assessment_type'].queryset)


class AssessmentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner")
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.competitor_role = CompetitionRole.objects.create(
            code="competitor-test",
            name="选手",
            category=CompetitionRole.Category.COMPETITOR,
        )
        self.expert_role = CompetitionRole.objects.create(
            code="expert-test",
            name="专家",
            category=CompetitionRole.Category.EXPERT,
        )
        self.assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
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
            assessment_type=get_mock_assessment_type(),
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

    def test_participant_can_snapshot_user_competition_person_or_temporary_person(self):
        self.user.first_name = "三"
        self.user.last_name = "张"
        self.user.save(update_fields=["first_name", "last_name"])
        user_participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            user=self.user,
            role=self.competitor_role,
            display_name="",
        )
        self.assertEqual(user_participant.display_name, "张三")

        person = CompetitionPerson.objects.create(
            name="长期专家",
            organization="示例单位",
            country_or_region="中国",
        )
        person_participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            competition_person=person,
            role=self.expert_role,
            display_name="",
        )
        self.assertEqual(person_participant.display_name, "长期专家")
        self.assertEqual(person_participant.organization, "示例单位")
        self.assertEqual(person_participant.country_or_region, "中国")

        temporary = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            role=self.expert_role,
            display_name="临时裁判",
        )
        self.assertEqual(temporary.display_name, "临时裁判")

    def test_participant_snapshot_is_not_changed_with_source_record(self):
        person = CompetitionPerson.objects.create(
            name="原姓名",
            organization="原单位",
            country_or_region="原地区",
        )
        participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            competition_person=person,
            role=self.expert_role,
            display_name="",
        )
        person.name = "新姓名"
        person.organization = "新单位"
        person.country_or_region = "新地区"
        person.save()
        participant.save()

        participant.refresh_from_db()
        self.assertEqual(participant.display_name, "原姓名")
        self.assertEqual(participant.organization, "原单位")
        self.assertEqual(participant.country_or_region, "原地区")

    def test_participant_rejects_two_linked_sources(self):
        person = CompetitionPerson.objects.create(name="专家")
        with self.assertRaisesMessage(ValidationError, "不能同时关联"):
            AssessmentParticipant.objects.create(
                assessment=self.assessment,
                user=self.user,
                competition_person=person,
                role=self.expert_role,
                display_name="冲突人员",
            )

    def test_module_scheduled_end_is_derived(self):
        started_at = timezone.make_aware(datetime(2026, 1, 1, 9, 30))
        module = AssessmentModule.objects.create(
            assessment=self.assessment,
            code="A",
            name="模块 A",
            scheduled_start_at=started_at,
            duration_minutes=90,
        )
        self.assertEqual(module.scheduled_end_at, started_at + timedelta(minutes=90))

    def test_final_result_supports_multiple_scores_and_awards(self):
        participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            display_name="选手",
            role=self.competitor_role,
        )
        final_result = AssessmentFinalResult.objects.create(
            participant=participant,
            rank=1,
            is_official=True,
            confirmed_by=self.user,
            confirmed_at=timezone.now(),
        )
        AssessmentFinalScore.objects.create(
            final_result=final_result,
            score_type=AssessmentFinalScore.ScoreType.RAW,
            label="原始总分",
            value="86.3500",
            max_value="100.0000",
        )
        AssessmentFinalScore.objects.create(
            final_result=final_result,
            score_type=AssessmentFinalScore.ScoreType.WORLDSKILLS,
            label="WorldSkills 标准化成绩",
            value="712.0000",
        )
        gold = AssessmentAward.objects.create(
            assessment=self.assessment,
            code="gold",
            name="金牌",
            category=AssessmentAward.Category.GOLD,
        )
        best_newcomer = AssessmentAward.objects.create(
            assessment=self.assessment,
            code="best-newcomer",
            name="最佳新人",
        )
        AssessmentResultAward.objects.create(final_result=final_result, award=gold)
        AssessmentResultAward.objects.create(final_result=final_result, award=best_newcomer)

        self.assertEqual(final_result.scores.count(), 2)
        self.assertEqual(final_result.awards.count(), 2)
        self.assertIsNone(final_result.scores.get(score_type="worldskills").max_value)
        self.assertEqual(final_result.assessment, self.assessment)

    def test_final_result_requires_competitor_and_award_from_same_assessment(self):
        expert = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            display_name="专家",
            role=self.expert_role,
        )
        with self.assertRaisesMessage(ValidationError, "只有选手类"):
            AssessmentFinalResult.objects.create(participant=expert)

        participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            display_name="选手",
            role=self.competitor_role,
        )
        final_result = AssessmentFinalResult.objects.create(participant=participant)
        other_assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name="另一场",
            code="FINAL-OTHER",
            start_date=date(2026, 2, 1),
            created_by=self.user,
        )
        other_award = AssessmentAward.objects.create(
            assessment=other_assessment,
            code="gold",
            name="金牌",
            category=AssessmentAward.Category.GOLD,
        )
        with self.assertRaisesMessage(ValidationError, "必须属于最终结果对应"):
            AssessmentResultAward.objects.create(final_result=final_result, award=other_award)


class AssessmentFormViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="assessment-form-admin")
        self.project = SkillProject.objects.create(code="FORM", name="表单测试项目")
        self.assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name="表单测试考核",
            code="FORM-ASSESSMENT",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 2),
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def test_create_and_edit_forms_use_shared_single_column_layout(self):
        urls = [
            reverse("assessments:assessment_create"),
            reverse("assessments:assessment_edit", args=[self.assessment.pk]),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "common/form.html")
                self.assertContains(response, 'class="flex flex-col gap-4"')
                self.assertNotContains(response, "md:grid-cols-2")

    def test_edit_form_renders_existing_dates_in_html_date_format(self):
        response = self.client.get(reverse("assessments:assessment_edit", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn('value="2026-04-01"', str(form["start_date"]))
        self.assertIn('value="2026-04-02"', str(form["end_date"]))

    def test_edit_form_can_change_from_current_status_to_any_status(self):
        self.assertNotIn("status", AssessmentForm().fields)
        self.assertEqual(
            [value for value, _label in AssessmentUpdateForm().fields["status"].choices],
            list(Assessment.Status.values),
        )

        url = reverse("assessments:assessment_edit", args=[self.assessment.pk])
        for status in Assessment.Status.values:
            with self.subTest(status=status):
                response = self.client.post(
                    url,
                    {
                        "skill_project": self.project.pk,
                        "series": "",
                        "level": "",
                        "training_cycle": "",
                        "assessment_type": get_mock_assessment_type().pk,
                        "status": status,
                        "name": self.assessment.name,
                        "code": self.assessment.code,
                        "start_date": "2026-04-01",
                        "end_date": "2026-04-02",
                        "location": "",
                        "description": "",
                    },
                )
                self.assertRedirects(response, reverse("assessments:assessment_detail", args=[self.assessment.pk]))
                self.assessment.refresh_from_db()
                self.assertEqual(self.assessment.status, status)

    def test_list_type_filter_keeps_stable_code_query_parameter(self):
        other_type = AssessmentType.objects.create(
            code="other-filter-type",
            name="其他筛选类型",
        )
        other_assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=other_type,
            name="不应出现的其他类型考核",
            code="OTHER-FILTER-ASSESSMENT",
            start_date=date(2026, 5, 1),
            created_by=self.user,
        )

        response = self.client.get(
            reverse("assessments:assessment_list"),
            {"type": get_mock_assessment_type().code},
        )

        self.assertContains(response, self.assessment.name)
        self.assertNotContains(response, other_assessment.name)


class AssessmentScopeSelectorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="linux-assessor")
        self.owner = User.objects.create_user(username="assessment-owner")
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.linux = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.windows = TechnicalDomain.objects.create(skill_project=self.project, code="WIN", name="Windows")
        self.assessment = self._assessment("LINUX-ASSESSMENT", "Linux 考核")
        self.other_assessment = self._assessment("WINDOWS-ASSESSMENT", "Windows 考核")
        self.linux_module = self._module(self.assessment, "L", self.linux)
        self.windows_module = self._module(self.other_assessment, "W", self.windows)
        self.cross_module = AssessmentModule.objects.create(
            assessment=self.assessment,
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
        group = Group.objects.create(name="Linux 评测维护")
        group.permissions.add(
            *Permission.objects.filter(
                content_type__app_label="assessments",
                codename__in=["view_assessment", "change_assessmentmodule"],
            )
        )
        TechnicalDomainGroupScope.objects.create(group=group, technical_domain=self.linux)
        self.user.groups.add(group)
        self.user = User.objects.get(pk=self.user.pk)

    def _assessment(self, code, name):
        return Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name=name,
            code=code,
            start_date=date(2026, 1, 1),
            created_by=self.owner,
        )

    def _module(self, assessment, code, domain):
        module = AssessmentModule.objects.create(assessment=assessment, code=code, name=code)
        AssessmentModuleDomain.objects.create(
            assessment_module=module,
            technical_domain=domain,
            role=AssessmentModuleDomain.Role.PRIMARY,
        )
        return module

    def test_single_domain_uses_group_permission_and_scope(self):
        self.assertIn(self.linux_module, manageable_assessment_modules_for(self.user))
        self.assertNotIn(self.windows_module, manageable_assessment_modules_for(self.user))
        self.assertNotIn(self.cross_module, manageable_assessment_modules_for(self.user))

    def test_cross_domain_module_requires_explicit_coach_assignment(self):
        AssessmentModuleCoach.objects.create(assessment_module=self.cross_module, user=self.user)

        self.assertIn(self.cross_module, manageable_assessment_modules_for(self.user))

    def test_participant_visibility_remains_independent_of_domain_scope(self):
        self.assertNotIn(self.other_assessment, visible_assessments_for(self.user))
        AssessmentParticipant.objects.create(
            assessment=self.other_assessment,
            user=self.user,
            role=CompetitionRole.objects.create(
                code="staff-scope-test",
                name="工作人员",
                category=CompetitionRole.Category.STAFF,
            ),
            display_name="Linux 评测人员",
        )

        self.assertIn(self.other_assessment, visible_assessments_for(self.user))


class AssessmentWorkspaceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="workspace-owner")
        self.coach = User.objects.create_user(username="workspace-linux-coach")
        self.project = SkillProject.objects.create(code="WORKSPACE", name="工作台测试项目")
        self.linux = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="WORKSPACE-LINUX",
            name="Linux",
        )
        self.windows = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="WORKSPACE-WINDOWS",
            name="Windows",
        )
        self.assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name="评测工作台",
            code="WORKSPACE-ASSESSMENT",
            start_date=date(2026, 6, 1),
            created_by=self.owner,
        )
        self.linux_module = self._module("L", "可见 Linux 模块", self.linux)
        self.windows_module = self._module("W", "隐藏 Windows 模块", self.windows)
        self.cross_module = AssessmentModule.objects.create(
            assessment=self.assessment,
            code="CROSS",
            name="隐藏跨领域模块",
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
        self.linux_scheme = self._scheme(self.linux_module, "L", "可见 Linux 评分方案")
        self.windows_scheme = self._scheme(self.windows_module, "W", "隐藏 Windows 评分方案")
        self.skill = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.linux,
            name="Linux 服务部署",
        )
        self.windows_skill = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.windows,
            name="Windows 服务部署",
        )
        competitor_role = CompetitionRole.objects.create(
            code="workspace-competitor",
            name="选手",
            category=CompetitionRole.Category.COMPETITOR,
        )
        self.participant = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            role=competitor_role,
            display_name="工作台选手",
        )
        self.linux_evidence = KnowledgeEvidence.objects.create(
            skill_project=self.project,
            assessment_module=self.linux_module,
            source_type=KnowledgeEvidence.SourceType.SCORING_ASPECT,
            scoring_aspect=self.linux_scheme.aspects.get(),
            title="可见 Linux 考点",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
            created_by=self.owner,
        )
        EvidenceSkillMap.objects.create(
            evidence=self.linux_evidence,
            skill=self.skill,
            weight=Decimal("1"),
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        ScoringResult.objects.create(
            participant=self.participant,
            aspect=self.linux_scheme.aspects.get(),
            score_awarded=Decimal("8"),
        )
        self.windows_evidence = KnowledgeEvidence.objects.create(
            skill_project=self.project,
            assessment_module=self.windows_module,
            source_type=KnowledgeEvidence.SourceType.SCORING_ASPECT,
            scoring_aspect=self.windows_scheme.aspects.get(),
            title="隐藏 Windows 考点",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
            created_by=self.owner,
        )
        EvidenceSkillMap.objects.create(
            evidence=self.windows_evidence,
            skill=self.windows_skill,
            weight=Decimal("1"),
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        ScoringResult.objects.create(
            participant=self.participant,
            aspect=self.windows_scheme.aspects.get(),
            score_awarded=Decimal("1"),
        )
        group = Group.objects.create(name="工作台 Linux 权限")
        permission_names = [
            "assessments.view_assessment",
            "assessments.view_assessmentmodule",
            "assessments.view_assessmentparticipant",
            "assessments.view_assessmentdocument",
            "assessments.view_assessmentfinalresult",
            "scoring.view_scoringscheme",
            "scoring.add_scoringscheme",
            "scoring.view_scoringresult",
            "scoring.view_all_scoringresult",
            "evidence.view_knowledgeevidence",
            "standards.view_skill",
        ]
        group.permissions.add(
            *[
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
                for app_label, codename in (name.split(".", maxsplit=1) for name in permission_names)
            ]
        )
        TechnicalDomainGroupScope.objects.create(group=group, technical_domain=self.linux)
        self.coach.groups.add(group)
        self.coach = User.objects.get(pk=self.coach.pk)
        self.client.force_login(self.coach)

    def _module(self, code, name, domain):
        module = AssessmentModule.objects.create(assessment=self.assessment, code=code, name=name)
        AssessmentModuleDomain.objects.create(
            assessment_module=module,
            technical_domain=domain,
            role=AssessmentModuleDomain.Role.PRIMARY,
        )
        return module

    @staticmethod
    def _scheme(module, code, title):
        scheme = ScoringScheme.objects.create(
            assessment_module=module,
            title=title,
            module_code=code,
            module_name=module.name,
            total_mark=Decimal("10"),
        )
        subcriterion = ScoringSubCriterion.objects.create(scheme=scheme, code=f"{code}1", name="评分子项")
        ScoringAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion,
            code=f"{code}1.1",
            aspect_type=ScoringAspect.AspectType.MEASUREMENT,
            description="服务可用",
            max_mark=Decimal("10"),
            source_row_number=1,
        )
        return scheme

    def test_workspace_has_seven_server_rendered_tabs(self):
        response = self.client.get(reverse("assessments:assessment_detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 200)
        for label in ["概览", "模块与资料", "人员", "评分", "最终结果", "考点与技能", "分析"]:
            self.assertContains(response, label)
        self.assertContains(response, "基本信息")
        self.assertNotContains(response, "进入在线评分")

    def test_workspace_tabs_preserve_module_scoring_and_evidence_scope(self):
        url = reverse("assessments:assessment_detail", args=[self.assessment.pk])

        module_response = self.client.get(url, {"tab": "modules"})
        self.assertContains(module_response, "可见 Linux 模块")
        self.assertContains(
            module_response,
            f"{reverse('scoring:scheme_import')}?module={self.linux_module.pk}",
        )
        self.assertNotContains(module_response, "隐藏 Windows 模块")
        self.assertNotContains(module_response, "隐藏跨领域模块")

        scoring_response = self.client.get(url, {"tab": "scoring"})
        self.assertContains(scoring_response, "可见 Linux 评分方案")
        self.assertNotContains(scoring_response, "隐藏 Windows 评分方案")

        evidence_response = self.client.get(url, {"tab": "evidence"})
        self.assertContains(evidence_response, "可见 Linux 考点")
        self.assertNotContains(evidence_response, "隐藏 Windows 考点")
        self.assertContains(evidence_response, reverse("standards:skill_detail", args=[self.skill.pk]))

        analysis_response = self.client.get(url, {"tab": "analysis"})
        self.assertTrue(analysis_response.context["can_view_skill_analysis"])
        skill_row = analysis_response.context["assessment_skill_performance"][0]
        self.assertEqual(skill_row["skill_id"], self.skill.pk)
        self.assertEqual(skill_row["awarded_mark"], Decimal("8"))
        self.assertEqual(skill_row["mapped_max_mark"], Decimal("10"))
        self.assertEqual(skill_row["lost_mark"], Decimal("2"))
        self.assertEqual(skill_row["score_rate"], Decimal("80.0"))
        self.assertEqual(len(analysis_response.context["assessment_skill_performance"]), 1)
        self.assertContains(analysis_response, reverse("standards:skill_detail", args=[self.skill.pk]))
        self.assertNotContains(analysis_response, "Windows 服务部署")

        skill_response = self.client.get(reverse("standards:skill_detail", args=[self.skill.pk]))
        self.assertTrue(skill_response.context["can_view_assessment_performance"])
        self.assertEqual(skill_response.context["assessment_performance"]["awarded_mark"], Decimal("8"))
        self.assertContains(skill_response, "最近得失分趋势")
        self.assertContains(skill_response, "工作台选手")

        people_response = self.client.get(url, {"tab": "people"})
        self.assertContains(people_response, "工作台选手")

    def test_unknown_workspace_tab_falls_back_to_overview(self):
        response = self.client.get(
            reverse("assessments:assessment_detail", args=[self.assessment.pk]),
            {"tab": "not-a-tab"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "基本信息")

    def test_modules_tab_renders_responsive_document_lists(self):
        permission = Permission.objects.get(
            content_type__app_label="assessments",
            codename="add_assessmentdocument",
        )
        self.coach.groups.get(name="工作台 Linux 权限").permissions.add(permission)
        self.coach = User.objects.get(pk=self.coach.pk)
        self.client.force_login(self.coach)

        AssessmentDocument.objects.create(
            assessment=self.assessment,
            document_type=AssessmentDocument.DocumentType.MARKING_STANDARD,
            title="公共评分标准",
            file="public/公共评分标准.pdf",
            original_filename="公共评分标准.pdf",
            file_sha256="a" * 64,
            uploaded_by=self.owner,
        )
        older_document = AssessmentDocument.objects.create(
            assessment=self.assessment,
            module=self.linux_module,
            document_type=AssessmentDocument.DocumentType.ATTACHMENT,
            title="旧版模块说明",
            file="modules/模块旧版.pdf",
            original_filename="模块旧版.pdf",
            file_sha256="b" * 64,
            uploaded_by=self.owner,
        )
        newer_document = AssessmentDocument.objects.create(
            assessment=self.assessment,
            module=self.linux_module,
            document_type=AssessmentDocument.DocumentType.TEST_PROJECT,
            title="新版模块说明",
            version="V2",
            file="modules/模块新版.docx",
            original_filename="模块新版.docx",
            file_sha256="c" * 64,
            uploaded_by=self.owner,
        )
        AssessmentDocument.objects.filter(pk=older_document.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        AssessmentDocument.objects.filter(pk=newer_document.pk).update(created_at=timezone.now())
        newer_document.refresh_from_db()

        response = self.client.get(
            reverse("assessments:assessment_detail", args=[self.assessment.pk]),
            {"tab": "modules"},
        )

        self.assertEqual(response.status_code, 200)
        for text in [
            "公共资料",
            "模块资料",
            "公共评分标准.pdf",
            "模块旧版.pdf",
            "模块新版.docx",
            "公共评分标准",
            "新版模块说明",
            "资料类型",
            "版本",
            "文件大小",
            "上传者",
            "上传时间",
            "V2",
            "未知",
            self.owner.display_name,
            timezone.localtime(newer_document.created_at).strftime("%Y-%m-%d %H:%M"),
        ]:
            self.assertContains(response, text)
        self.assertContains(response, "icon-[tabler--file-type-pdf]")
        self.assertContains(response, "icon-[tabler--file-type-doc]")
        self.assertContains(response, "icon-[tabler--upload]")
        self.assertContains(response, "上传模块资料")
        self.assertContains(response, "xl:grid-cols-4")
        self.assertNotContains(response, "xl:grid-cols-2")

        content = response.content.decode()
        self.assertLess(content.index("模块新版.docx"), content.index("模块旧版.pdf"))
        self.assertIn(reverse("assessments:document_detail", args=[newer_document.pk]), content)
        self.assertIn(reverse("assessments:document_download", args=[newer_document.pk]), content)
        self.assertIn(f">{newer_document.filename}</a>", content)

    def test_modules_tab_keeps_empty_general_documents_section(self):
        response = self.client.get(
            reverse("assessments:assessment_detail", args=[self.assessment.pk]),
            {"tab": "modules"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "公共资料")
        self.assertContains(response, "暂无公共资料")

    def test_general_document_upload_returns_to_workspace_modules_tab(self):
        view = AssessmentDocumentCreateView()
        view.object = AssessmentDocument(assessment=self.assessment)

        self.assertEqual(
            view.get_success_url(),
            f"{reverse('assessments:assessment_detail', args=[self.assessment.pk])}?tab=modules",
        )

    def test_module_document_upload_still_returns_to_module_detail(self):
        view = AssessmentDocumentCreateView()
        view.object = AssessmentDocument(assessment=self.assessment, module=self.linux_module)

        self.assertEqual(
            view.get_success_url(),
            reverse("assessments:module_detail", args=[self.linux_module.pk]),
        )

    def test_workspace_does_not_expose_aggregate_scores_without_view_all_permission(self):
        student = User.objects.create_user(username="workspace-student")
        student_group = Group.objects.create(name="工作台选手权限")
        permission_names = [
            "assessments.view_assessment",
            "assessments.view_assessmentmodule",
            "scoring.view_scoringscheme",
            "scoring.view_scoringresult",
            "evidence.view_knowledgeevidence",
            "standards.view_skill",
        ]
        student_group.permissions.add(
            *[
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
                for app_label, codename in (name.split(".", maxsplit=1) for name in permission_names)
            ]
        )
        TechnicalDomainGroupScope.objects.create(group=student_group, technical_domain=self.linux)
        student.groups.add(student_group)
        student = User.objects.get(pk=student.pk)
        self.client.force_login(student)

        response = self.client.get(
            reverse("assessments:assessment_detail", args=[self.assessment.pk]),
            {"tab": "analysis"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_view_skill_analysis"])
        self.assertEqual(response.context["assessment_skill_performance"], [])
        self.assertIsNone(response.context["workspace_modules"][0].scoring_summary)
        self.assertContains(response, "需要“查看全部评分结果”和“查看考点证据”权限")

        skill_response = self.client.get(reverse("standards:skill_detail", args=[self.skill.pk]))
        self.assertEqual(skill_response.status_code, 200)
        self.assertFalse(skill_response.context["can_view_assessment_performance"])
        self.assertNotContains(skill_response, "工作台选手")


class CompetitionCatalogViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="competition-catalog-manager")
        permissions = Permission.objects.filter(
            content_type__app_label="assessments",
            codename__in=[
                "view_competitionperson",
                "add_competitionperson",
                "change_competitionperson",
                "view_competitionrole",
                "add_competitionrole",
                "change_competitionrole",
            ],
        )
        self.user.user_permissions.add(*permissions)
        self.user = User.objects.get(pk=self.user.pk)
        self.person = CompetitionPerson.objects.create(name="长期专家", organization="赛事机构")
        self.role = CompetitionRole.objects.create(
            code="catalog-expert",
            name="专家",
            category=CompetitionRole.Category.EXPERT,
        )
        self.client.force_login(self.user)

    def test_catalog_lists_are_permissioned_and_searchable(self):
        people_response = self.client.get(
            reverse("assessments:competition_person_list"),
            {"q": "长期"},
        )
        role_response = self.client.get(reverse("assessments:competition_role_list"))

        self.assertEqual(people_response.status_code, 200)
        self.assertContains(people_response, "长期专家")
        self.assertContains(people_response, "新增长期赛事人员")
        self.assertEqual(role_response.status_code, 200)
        self.assertContains(role_response, "catalog-expert")
        self.assertContains(role_response, "新增赛事角色")

        outsider = User.objects.create_user(username="competition-catalog-outsider")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("assessments:competition_person_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("assessments:competition_role_list")).status_code, 403)

    def test_catalog_create_and_update_keep_global_people_and_roles_configurable(self):
        person_response = self.client.post(
            reverse("assessments:competition_person_create"),
            {
                "name": "赛事经理",
                "organization": "项目办公室",
                "country_or_region": "中国",
                "title": "项目经理",
                "email": "manager@example.com",
                "phone": "10086",
                "notes": "跨届复用",
                "metadata": "{}",
                "is_active": "on",
            },
        )
        self.assertRedirects(person_response, reverse("assessments:competition_person_list"))
        created_person = CompetitionPerson.objects.get(name="赛事经理")
        person_update_response = self.client.post(
            reverse("assessments:competition_person_edit", args=[created_person.pk]),
            {
                "name": "赛事经理（更新）",
                "organization": "项目办公室",
                "country_or_region": "中国",
                "title": "项目经理",
                "email": "manager@example.com",
                "phone": "10086",
                "notes": "跨届复用",
                "metadata": "{}",
                "is_active": "on",
            },
        )
        self.assertRedirects(person_update_response, reverse("assessments:competition_person_list"))
        created_person.refresh_from_db()
        self.assertEqual(created_person.name, "赛事经理（更新）")

        role_response = self.client.post(
            reverse("assessments:competition_role_create"),
            {
                "code": "venue-manager",
                "name": "场地经理",
                "category": CompetitionRole.Category.OFFICIAL,
                "description": "赛事角色配置",
                "order": 20,
                "is_active": "on",
            },
        )
        self.assertRedirects(role_response, reverse("assessments:competition_role_list"))
        created_role = CompetitionRole.objects.get(code="venue-manager")
        self.assertEqual(created_role.category, CompetitionRole.Category.OFFICIAL)


class AssessmentLifecycleAndFinalResultTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="final-owner")
        self.manager = User.objects.create_user(username="final-manager")
        self.student_one = User.objects.create_user(username="final-student-one")
        self.student_two = User.objects.create_user(username="final-student-two")
        self.outsider = User.objects.create_user(username="final-outsider")
        self.project = SkillProject.objects.create(code="FINAL", name="最终结果项目")
        self.assessment = Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name="最终结果评测",
            code="FINAL-ASSESSMENT",
            start_date=date(2026, 7, 1),
            created_by=self.owner,
        )
        self.module = AssessmentModule.objects.create(
            assessment=self.assessment,
            code="A",
            name="模块 A",
            counts_towards_ranking=True,
        )
        self.scheme = ScoringScheme.objects.create(
            assessment_module=self.module,
            title="最终结果评分方案",
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
        competitor_role = CompetitionRole.objects.create(
            code="final-competitor",
            name="选手",
            category=CompetitionRole.Category.COMPETITOR,
        )
        self.participant_one = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            user=self.student_one,
            role=competitor_role,
            display_name="选手一",
        )
        self.participant_two = AssessmentParticipant.objects.create(
            assessment=self.assessment,
            user=self.student_two,
            role=competitor_role,
            display_name="选手二",
        )
        self.result_one = ScoringResult.objects.create(
            participant=self.participant_one,
            aspect=self.aspect,
            score_awarded=Decimal("8"),
        )
        self.result_two = ScoringResult.objects.create(
            participant=self.participant_two,
            aspect=self.aspect,
            score_awarded=Decimal("6"),
        )
        manager_group = Group.objects.create(name="最终结果项目负责人")
        manager_group.permissions.add(
            *self._permissions(
                [
                    "assessments.view_assessment",
                    "assessments.view_all_assessment",
                    "assessments.change_assessment",
                    "assessments.change_all_assessment",
                    "assessments.view_assessmentmodule",
                    "assessments.view_assessmentparticipant",
                    "assessments.view_assessmentfinalresult",
                    "assessments.add_assessmentfinalresult",
                    "assessments.change_assessmentfinalresult",
                    "assessments.view_assessmentfinalscore",
                    "assessments.add_assessmentfinalscore",
                    "assessments.change_assessmentfinalscore",
                    "assessments.view_assessmentaward",
                    "assessments.add_assessmentaward",
                    "assessments.change_assessmentaward",
                    "assessments.view_assessmentresultaward",
                    "assessments.add_assessmentresultaward",
                    "assessments.change_assessmentresultaward",
                ]
            )
        )
        self.manager.groups.add(manager_group)
        self.manager = User.objects.get(pk=self.manager.pk)
        student_permissions = self._permissions(
            [
                "assessments.view_assessment",
                "assessments.view_assessmentparticipant",
                "assessments.view_assessmentfinalresult",
                "assessments.view_assessmentfinalscore",
                "assessments.view_assessmentaward",
                "assessments.view_assessmentresultaward",
            ]
        )
        self.student_one.user_permissions.add(*student_permissions)
        self.student_two.user_permissions.add(*student_permissions)
        self.student_one = User.objects.get(pk=self.student_one.pk)
        self.student_two = User.objects.get(pk=self.student_two.pk)

    @staticmethod
    def _permissions(permission_names):
        return [
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
            for app_label, codename in (name.split(".", maxsplit=1) for name in permission_names)
        ]

    def _complete_assessment(self):
        transition_assessment(self.assessment, "publish", self.manager)
        transition_assessment(self.assessment, "start", self.manager)
        completed = transition_assessment(self.assessment, "complete", self.manager)
        self.assessment = completed
        return completed

    def test_lifecycle_uses_explicit_valid_transitions_and_timestamps(self):
        self.assertNotIn("status", AssessmentForm().fields)
        published = transition_assessment(self.assessment, "publish", self.manager)
        self.assertEqual(published.status, Assessment.Status.PUBLISHED)
        started = transition_assessment(published, "start", self.manager)
        self.assertEqual(started.status, Assessment.Status.ACTIVE)
        self.assertIsNotNone(started.started_at)
        completed = transition_assessment(started, "complete", self.manager)
        self.assertEqual(completed.status, Assessment.Status.COMPLETED)
        self.assertIsNotNone(completed.completed_at)
        with self.assertRaisesMessage(ValidationError, "不能执行"):
            transition_assessment(completed, "start", self.manager)
        with self.assertRaisesMessage(ValidationError, "必须先发布最终成绩"):
            transition_assessment(completed, "archive", self.manager)

        self.outsider.user_permissions.add(
            *self._permissions(["assessments.change_assessment"])
        )
        self.outsider = User.objects.get(pk=self.outsider.pk)
        with self.assertRaises(PermissionDenied):
            transition_assessment(self.assessment, "cancel", self.outsider)

    def test_calculated_preview_does_not_create_official_result(self):
        preview = calculated_final_result_preview(self.assessment)

        self.assertEqual([item["participant"] for item in preview], [self.participant_one, self.participant_two])
        self.assertEqual([item["raw_score"] for item in preview], [Decimal("8"), Decimal("6")])
        self.assertEqual([item["rank"] for item in preview], [1, 2])
        self.assertEqual(preview[0]["percentage"], Decimal("80.0000"))
        self.assertFalse(AssessmentFinalResult.objects.exists())

    def test_generate_edit_multi_scores_awards_and_reconfirmation(self):
        self._complete_assessment()
        summary = generate_final_results(self.assessment, self.manager)
        self.assertEqual(summary["created_count"], 2)
        final_result = AssessmentFinalResult.objects.get(participant=self.participant_one)
        self.assertFalse(final_result.is_official)
        self.assertEqual(final_result.rank, 1)
        self.assertEqual(
            set(final_result.scores.values_list("score_type", flat=True)),
            {AssessmentFinalScore.ScoreType.RAW, AssessmentFinalScore.ScoreType.PERCENTAGE},
        )
        confirm_final_result(final_result, self.manager)
        award = create_assessment_award(
            self.assessment,
            self.manager,
            code="best",
            name="最佳选手",
            category=AssessmentAward.Category.OTHER,
            description="",
            order=1,
        )

        updated = update_final_result_details(
            final_result,
            self.manager,
            rank=1,
            notes="人工复核",
            awards=[award],
            score_rows=[
                {
                    "score_id": None,
                    "delete": False,
                    "score_type": AssessmentFinalScore.ScoreType.WORLDSKILLS,
                    "label": "WorldSkills 标准化成绩",
                    "value": Decimal("712"),
                    "max_value": None,
                    "order": 20,
                }
            ],
        )

        self.assertFalse(updated.is_official)
        self.assertIsNone(updated.confirmed_at)
        self.assertEqual(updated.notes, "人工复核")
        self.assertEqual(updated.awards.get(), award)
        worldskills = updated.scores.get(score_type=AssessmentFinalScore.ScoreType.WORLDSKILLS)
        self.assertEqual(worldskills.value, Decimal("712"))
        self.assertIsNone(worldskills.max_value)

    def test_regeneration_removes_stale_generated_percentage_when_total_becomes_zero(self):
        self._complete_assessment()
        generate_final_results(self.assessment, self.manager)
        final_result = AssessmentFinalResult.objects.get(participant=self.participant_one)
        self.assertTrue(
            final_result.scores.filter(
                score_type=AssessmentFinalScore.ScoreType.PERCENTAGE,
                label="百分制成绩",
            ).exists()
        )

        self.aspect.max_mark = Decimal("0")
        self.aspect.save(update_fields=["max_mark"])
        generate_final_results(self.assessment, self.manager)

        self.assertFalse(
            final_result.scores.filter(
                score_type=AssessmentFinalScore.ScoreType.PERCENTAGE,
                label="百分制成绩",
            ).exists()
        )
        raw_score = final_result.scores.get(
            score_type=AssessmentFinalScore.ScoreType.RAW,
            label="原始总分",
        )
        self.assertEqual(raw_score.max_value, Decimal("0"))

    def test_publish_boundary_exposes_only_each_students_own_official_result(self):
        self._complete_assessment()
        generate_final_results(self.assessment, self.manager)
        final_one = AssessmentFinalResult.objects.get(participant=self.participant_one)
        final_two = AssessmentFinalResult.objects.get(participant=self.participant_two)
        self.assertFalse(visible_final_results_for(self.student_one, self.assessment).exists())
        self.assertEqual(visible_final_results_for(self.manager, self.assessment).count(), 2)

        confirm_final_result(final_one, self.manager)
        with self.assertRaisesMessage(ValidationError, "每名选手"):
            publish_final_results(self.assessment, self.manager)
        confirm_final_result(final_two, self.manager)
        published = publish_final_results(self.assessment, self.manager)
        self.assertIsNotNone(published.results_published_at)
        self.assessment = published

        self.assertEqual(list(visible_final_results_for(self.student_one, published)), [final_one])
        self.assertEqual(list(visible_final_results_for(self.student_two, published)), [final_two])
        with self.assertRaisesMessage(ValidationError, "已发布"):
            update_final_result_details(
                final_one,
                self.manager,
                rank=2,
                notes="不应允许",
                awards=[],
                score_rows=[],
            )
        archived = transition_assessment(published, "archive", self.manager)
        self.assertEqual(archived.status, Assessment.Status.ARCHIVED)

    def test_lifecycle_and_result_actions_are_post_only(self):
        self.client.force_login(self.manager)
        action_url = reverse("assessments:assessment_action", args=[self.assessment.pk, "publish"])
        self.assertEqual(self.client.get(action_url).status_code, 405)
        self.assertEqual(self.client.post(action_url).status_code, 302)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, Assessment.Status.PUBLISHED)

        transition_assessment(self.assessment, "start", self.manager)
        self.assessment = transition_assessment(self.assessment, "complete", self.manager)
        generate_url = reverse("assessments:final_results_generate", args=[self.assessment.pk])
        self.assertEqual(self.client.get(generate_url).status_code, 405)
        self.assertEqual(self.client.post(generate_url).status_code, 302)
        final_result = AssessmentFinalResult.objects.get(participant=self.participant_one)
        response = self.client.get(reverse("assessments:final_result_edit", args=[final_result.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "多评分体系成绩")


class AssessmentPermissionBoundaryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="assessment-permission-owner")
        self.other_owner = User.objects.create_user(username="assessment-permission-other-owner")
        self.manager = User.objects.create_user(username="assessment-project-manager")
        self.linux_coach = User.objects.create_user(username="assessment-linux-coach")
        self.student = User.objects.create_user(username="assessment-student")
        self.outsider = User.objects.create_user(username="assessment-outsider")
        self.split_scope_user = User.objects.create_user(username="assessment-split-scope")
        self.project = SkillProject.objects.create(code="PERMISSION", name="权限测试项目")
        self.linux = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="PERMISSION-LINUX",
            name="Linux",
        )
        self.windows = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="PERMISSION-WINDOWS",
            name="Windows",
        )
        self.linux_assessment = self._assessment("PERMISSION-LINUX", self.owner)
        self.windows_assessment = self._assessment("PERMISSION-WINDOWS", self.other_owner)
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
        self.competitor_role = CompetitionRole.objects.create(
            code="permission-competitor",
            name="选手",
            category=CompetitionRole.Category.COMPETITOR,
        )
        self.student_participant = AssessmentParticipant.objects.create(
            assessment=self.linux_assessment,
            user=self.student,
            role=self.competitor_role,
            display_name="Linux 选手",
        )
        self.windows_participant = AssessmentParticipant.objects.create(
            assessment=self.windows_assessment,
            role=self.competitor_role,
            display_name="Windows 选手",
        )
        self.linux_document = AssessmentDocument.objects.create(
            assessment=self.linux_assessment,
            module=self.linux_module,
            document_type=AssessmentDocument.DocumentType.TEST_PROJECT,
            title="Linux 试题",
            file="linux.pdf",
            original_filename="linux.pdf",
            file_sha256="1" * 64,
            uploaded_by=self.owner,
        )
        self.windows_document = AssessmentDocument.objects.create(
            assessment=self.windows_assessment,
            module=self.windows_module,
            document_type=AssessmentDocument.DocumentType.TEST_PROJECT,
            title="Windows 试题",
            file="windows.pdf",
            original_filename="windows.pdf",
            file_sha256="2" * 64,
            uploaded_by=self.other_owner,
        )
        self.linux_coach = self._grant_group(
            self.linux_coach,
            "Linux 评测权限",
            [
                "assessments.view_assessment",
                "assessments.view_assessmentmodule",
                "assessments.change_assessmentmodule",
                "assessments.view_assessmentparticipant",
                "assessments.add_assessmentparticipant",
                "assessments.view_assessmentdocument",
                "assessments.add_assessmentdocument",
            ],
            [self.linux],
        )

    def _assessment(self, code, owner):
        return Assessment.objects.create(
            skill_project=self.project,
            assessment_type=get_mock_assessment_type(),
            name=code,
            code=code,
            start_date=date(2026, 3, 1),
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

    def _create_preview_document(self, filename, content):
        document = AssessmentDocument.objects.create(
            assessment=self.linux_assessment,
            module=self.linux_module,
            document_type=AssessmentDocument.DocumentType.ATTACHMENT,
            title="预览附件",
            description="用于验证通用预览",
            version="V1",
            file=SimpleUploadedFile(filename, content),
            original_filename=filename,
            uploaded_by=self.owner,
        )
        self.addCleanup(document.file.delete, False)
        return document

    def test_assessment_update_uses_owner_or_project_wide_permission(self):
        self.owner.user_permissions.add(*self._permissions(["assessments.change_assessment"]))
        self.owner = User.objects.get(pk=self.owner.pk)
        self.assertIn(self.linux_assessment, manageable_assessments_for(self.owner))
        self.assertNotIn(self.windows_assessment, manageable_assessments_for(self.owner))

        self.manager = self._grant_group(
            self.manager,
            "评测项目负责人",
            [
                "assessments.view_assessment",
                "assessments.view_all_assessment",
                "assessments.change_assessment",
                "assessments.change_all_assessment",
            ],
        )
        self.assertIn(self.windows_assessment, manageable_assessments_for(self.manager))

        self.client.force_login(self.manager)
        response = self.client.get(reverse("assessments:assessment_edit", args=[self.windows_assessment.pk]))
        self.assertEqual(response.status_code, 200)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("assessments:assessment_edit", args=[self.windows_assessment.pk]))
        self.assertEqual(response.status_code, 404)

        domain_editor = self._grant_group(
            self.split_scope_user,
            "领域内只读及顶层编辑权限",
            ["assessments.view_assessment", "assessments.change_assessment"],
            [self.linux],
        )
        self.assertIn(self.linux_assessment, visible_assessments_for(domain_editor))
        self.assertNotIn(self.linux_assessment, manageable_assessments_for(domain_editor))
        self.client.force_login(domain_editor)
        action_url = reverse("assessments:assessment_action", args=[self.linux_assessment.pk, "publish"])
        response = self.client.post(action_url)
        self.assertEqual(response.status_code, 404)
        self.linux_assessment.refresh_from_db()
        self.assertEqual(self.linux_assessment.status, Assessment.Status.DRAFT)

    def test_module_scope_requires_same_group_permission_and_scope(self):
        self.assertIn(self.linux_module, visible_assessment_modules_for(self.linux_coach))
        self.assertNotIn(self.windows_module, visible_assessment_modules_for(self.linux_coach))
        self.assertNotIn(self.cross_module, visible_assessment_modules_for(self.linux_coach))

        AssessmentModuleCoach.objects.create(assessment_module=self.cross_module, user=self.linux_coach)
        self.assertIn(self.cross_module, visible_assessment_modules_for(self.linux_coach))

        self.split_scope_user.user_permissions.add(*self._permissions(["assessments.view_assessmentmodule"]))
        scope_only_group = Group.objects.create(name="只有 Linux Scope")
        TechnicalDomainGroupScope.objects.create(group=scope_only_group, technical_domain=self.linux)
        self.split_scope_user.groups.add(scope_only_group)
        self.split_scope_user = User.objects.get(pk=self.split_scope_user.pk)
        self.assertNotIn(self.linux_module, visible_assessment_modules_for(self.split_scope_user))

    def test_module_create_accepts_assessment_query_parameter(self):
        self.owner.user_permissions.add(*self._permissions(["assessments.add_assessmentmodule"]))
        self.owner = User.objects.get(pk=self.owner.pk)
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("assessments:module_create"),
            {"assessment": self.linux_assessment.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.linux, response.context["form"].fields["domains"].queryset)

    def test_participant_detail_and_document_visibility_follow_assessment_scope(self):
        self.assertIn(self.student_participant, visible_assessment_participants_for(self.linux_coach))
        self.assertNotIn(self.windows_participant, visible_assessment_participants_for(self.linux_coach))
        self.assertIn(self.linux_document, visible_documents_for(self.linux_coach))
        self.assertNotIn(self.windows_document, visible_documents_for(self.linux_coach))

        self.client.force_login(self.linux_coach)
        allowed = self.client.get(reverse("assessments:participant_detail", args=[self.student_participant.pk]))
        denied = self.client.get(reverse("assessments:participant_detail", args=[self.windows_participant.pk]))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 404)

    def test_document_detail_preview_and_download_follow_document_scope(self):
        document = self._create_preview_document("linux-preview.pdf", b"%PDF-1.7\npreview")
        self.client.force_login(self.linux_coach)

        detail_url = reverse("assessments:document_detail", args=[document.pk])
        preview_url = reverse("assessments:document_preview", args=[document.pk])
        download_url = reverse("assessments:document_download", args=[document.pk])
        detail_response = self.client.get(detail_url)
        preview_response = self.client.get(preview_url)
        download_response = self.client.get(download_url)

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "linux-preview.pdf")
        self.assertContains(detail_response, "预览附件")
        self.assertContains(detail_response, "其他附件")
        self.assertContains(detail_response, self.linux_assessment.name)
        self.assertContains(detail_response, self.linux_module.name)
        self.assertContains(detail_response, f'src="{preview_url}"')
        self.assertContains(detail_response, f'href="{download_url}"')
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response["Content-Type"], "application/pdf")
        self.assertIn("inline", preview_response["Content-Disposition"])
        self.assertEqual(download_response.status_code, 200)
        self.assertIn("attachment", download_response["Content-Disposition"])
        preview_response.close()
        download_response.close()

        for url_name in ["document_detail", "document_preview", "document_download"]:
            denied_response = self.client.get(
                reverse(f"assessments:{url_name}", args=[self.windows_document.pk])
            )
            self.assertEqual(denied_response.status_code, 404)

    def test_document_detail_escapes_text_and_handles_unsupported_or_missing_files(self):
        text_document = self._create_preview_document(
            "notes.txt",
            b"<script>alert(1)</script>",
        )
        office_document = self._create_preview_document("report.docx", b"PK\x03\x04office")
        self.client.force_login(self.linux_coach)

        text_response = self.client.get(
            reverse("assessments:document_detail", args=[text_document.pk])
        )
        office_response = self.client.get(
            reverse("assessments:document_detail", args=[office_document.pk])
        )
        missing_detail = self.client.get(
            reverse("assessments:document_detail", args=[self.linux_document.pk])
        )
        missing_preview = self.client.get(
            reverse("assessments:document_preview", args=[self.linux_document.pk])
        )
        missing_download = self.client.get(
            reverse("assessments:document_download", args=[self.linux_document.pk])
        )

        self.assertContains(text_response, "&lt;script&gt;alert(1)&lt;/script&gt;", html=False)
        self.assertNotContains(text_response, "<script>alert(1)</script>", html=False)
        self.assertContains(office_response, "该文件暂不支持在线预览")
        self.assertNotContains(office_response, "<iframe", html=False)
        self.assertContains(missing_detail, "文件不可用")
        self.assertEqual(missing_preview.status_code, 404)
        self.assertEqual(missing_download.status_code, 404)

    def test_module_detail_document_link_opens_preview_detail(self):
        self.client.force_login(self.linux_coach)

        response = self.client.get(
            reverse("assessments:module_detail", args=[self.linux_module.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("assessments:document_detail", args=[self.linux_document.pk])}"',
        )

    def test_create_forms_only_offer_in_scope_assessments_and_modules(self):
        participant_form = AssessmentParticipantForm(user=self.linux_coach)
        self.assertIn(self.linux_assessment, participant_form.fields["assessment"].queryset)
        self.assertNotIn(self.windows_assessment, participant_form.fields["assessment"].queryset)

        document_form = AssessmentDocumentForm(user=self.linux_coach)
        self.assertIn(self.linux_module, document_form.fields["module"].queryset)
        self.assertNotIn(self.windows_module, document_form.fields["module"].queryset)
        self.assertNotIn(self.cross_module, document_form.fields["module"].queryset)

    def test_participant_can_view_modules_but_outsider_cannot(self):
        self.student.user_permissions.add(
            *self._permissions(
                [
                    "assessments.view_assessment",
                    "assessments.view_assessmentmodule",
                ]
            )
        )
        self.student = User.objects.get(pk=self.student.pk)
        self.assertIn(self.linux_module, visible_assessment_modules_for(self.student))
        self.assertIn(self.cross_module, visible_assessment_modules_for(self.student))
        self.assertNotIn(self.windows_module, visible_assessment_modules_for(self.student))
        self.assertFalse(visible_assessment_modules_for(self.outsider).exists())
