from datetime import date
from decimal import Decimal
from io import StringIO
import importlib
from pathlib import Path
import shutil
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse

from competition_standards.models import CompetitionType, Project, StandardModule, StandardModuleSet, TrainingCycle
from core.constants import GROUP_COACH
from core.uploads import ASSESSMENT_TP_UPLOAD_SPEC

from marking.models import (
    MarkingAspect,
    MarkingParticipant,
    MarkingResult,
    MarkingScheme,
    MarkingSchemeImport,
    MarkingSubCriterion,
)
from marking.parser import PARSER_VERSION
from marking.services import get_content_type_for_target

from .models import Assessment, AssessmentAttachment, AssessmentModule
from .selectors import build_assessment_list_context, build_assessment_score_table_context


User = get_user_model()


def create_marking_score(assessment_module, user, score):
    content_type = get_content_type_for_target(assessment_module)
    scheme = MarkingScheme.objects.filter(
        target_content_type=content_type,
        target_object_id=assessment_module.pk,
    ).first()
    if scheme is None:
        source_import = MarkingSchemeImport.objects.create(
            file=f"schemes/{assessment_module.pk}.xlsx",
            original_filename=f"{assessment_module.module.code}.xlsx",
            file_sha256="0" * 64,
            parser_version=PARSER_VERSION,
            parse_summary={},
            target_content_type=content_type,
            target_object_id=assessment_module.pk,
        )
        scheme = MarkingScheme.objects.create(
            source_import=source_import,
            standard_module=assessment_module.module,
            target_content_type=content_type,
            target_object_id=assessment_module.pk,
            title=f"{assessment_module.module.code} 评分方案",
            module_code=assessment_module.module.code,
            module_name=assessment_module.module.name,
            total_mark=assessment_module.max_score,
            parser_version=PARSER_VERSION,
        )
        subcriterion = MarkingSubCriterion.objects.create(
            scheme=scheme,
            code=f"{assessment_module.module.code}1",
            name="默认子项",
            day_of_marking="1",
        )
        MarkingAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion,
            code=f"{assessment_module.module.code}1.1",
            aspect_type=MarkingAspect.AspectType.MEASUREMENT,
            description="默认评分点",
            command="CMP 导入结果",
            requirement="结果有效",
            max_mark=assessment_module.max_score,
            source_row_number=1,
        )
    aspect = scheme.aspects.first()
    participant, _ = MarkingParticipant.objects.update_or_create(
        scheme=scheme,
        user=user,
        defaults={"display_name": user.display_name, "sort_order": 0},
    )
    result, _ = MarkingResult.objects.update_or_create(
        participant=participant,
        aspect=aspect,
        defaults={"score_awarded": score, "source": MarkingResult.Source.IMPORTED},
    )
    return result


class AssessmentModuleOrderingTests(TestCase):
    def setUp(self):
        competition_type = CompetitionType.objects.create(
            code="WSC",
            name="世界技能大赛",
        )
        project = Project.objects.create(
            competition_type=competition_type,
            code="ITNSA",
            name="信息网络布线",
        )
        module_set = project.get_or_create_default_standard_module_set()
        training_cycle = TrainingCycle.objects.create(
            code="TC-ORDER",
            name="排序测试周期",
            project=project,
            module_set=module_set,
            start_date=date(2026, 1, 1),
        )
        self.assessment = Assessment.objects.create(
            name="2026 春季考核",
            training_cycle=training_cycle,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 2),
        )

        module_b = StandardModule.objects.create(project=project, code="B", name="模块 B")
        module_a = StandardModule.objects.create(project=project, code="A", name="模块 A")
        module_c = StandardModule.objects.create(project=project, code="C", name="模块 C")

        AssessmentModule.objects.create(
            assessment=self.assessment,
            module=module_b,
            sort_order=1,
        )
        AssessmentModule.objects.create(
            assessment=self.assessment,
            module=module_a,
            sort_order=1,
        )
        AssessmentModule.objects.create(
            assessment=self.assessment,
            module=module_c,
            sort_order=0,
        )

    def test_assessment_modules_are_ordered_by_sort_order_then_module_code(self):
        module_codes = list(
            self.assessment.assessmentmodule_set.values_list("module__code", flat=True)
        )

        self.assertEqual(module_codes, ["C", "A", "B"])


class AssessmentModuleAdminModuleQuerysetTests(TestCase):
    def setUp(self):
        competition_type = CompetitionType.objects.create(
            code="WSC-ADMIN",
            name="后台测试赛事",
        )
        self.project = Project.objects.create(
            competition_type=competition_type,
            code="ITNSA-ADMIN",
            name="后台测试项目",
        )
        self.current_module = StandardModule.objects.create(
            project=self.project,
            code="A",
            name="当前模块",
        )
        historical_module_set = StandardModuleSet.objects.create(
            project=self.project,
            code="2024",
            name="2024 版标准模块",
            is_current=False,
        )
        self.historical_module = StandardModule.objects.create(
            project=self.project,
            module_set=historical_module_set,
            code="B",
            name="历史模块",
        )
        self.training_cycle = TrainingCycle.objects.create(
            code="TC-ADMIN",
            name="后台测试周期",
            project=self.project,
            module_set=self.project.current_standard_module_set,
            start_date=date(2026, 1, 1),
        )
        self.assessment = Assessment.objects.create(
            name="后台测试考核",
            training_cycle=self.training_cycle,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 2),
        )
        self.request = RequestFactory().get(
            "/admin/assessments/assessmentmodule/add/",
            {"assessment": self.assessment.pk},
        )
        self.admin = admin.site._registry[AssessmentModule]

    def test_admin_module_field_only_shows_training_cycle_modules(self):
        field = AssessmentModule._meta.get_field("module")

        form_field = self.admin.formfield_for_foreignkey(field, self.request)

        self.assertEqual(list(form_field.queryset), [self.current_module])


class AssessmentsUrlTests(TestCase):
    def test_assessment_list_is_mounted_at_app_root(self):
        self.assertEqual(reverse("assessments:list"), "/assessments/")


class AssessmentRankingConfigurationTests(TestCase):
    def setUp(self):
        self.participant_a = User.objects.create_user(
            username="ranking-a",
            password="testpass123",
            first_name="学员甲",
        )
        self.participant_b = User.objects.create_user(
            username="ranking-b",
            password="testpass123",
            first_name="学员乙",
        )
        competition_type = CompetitionType.objects.create(
            code="WSC-RANK",
            name="排名规则测试赛事",
        )
        project = Project.objects.create(
            competition_type=competition_type,
            code="ITNSA-RANK",
            name="排名规则测试项目",
        )
        module_set = project.get_or_create_default_standard_module_set()
        self.training_cycle = TrainingCycle.objects.create(
            code="TC-RANK",
            name="排名规则测试周期",
            project=project,
            module_set=module_set,
            start_date=date(2026, 1, 1),
        )
        ranking_module = StandardModule.objects.create(
            project=project,
            code="A",
            name="模块 A",
            default_counts_towards_ranking=True,
        )
        english_module = StandardModule.objects.create(
            project=project,
            code="ENG",
            name="English Interview",
            default_counts_towards_ranking=False,
        )
        self.assessment = Assessment.objects.create(
            name="2026 排名规则考核",
            training_cycle=self.training_cycle,
            start_date=date(2026, 1, 10),
            end_date=date(2026, 1, 11),
        )
        self.assessment.participants.set([self.participant_a, self.participant_b])
        self.ranking_assessment_module = AssessmentModule.objects.create(
            assessment=self.assessment,
            module=ranking_module,
            sort_order=0,
            max_score=Decimal("25.00"),
            counts_towards_ranking=True,
        )
        self.non_ranking_assessment_module = AssessmentModule.objects.create(
            assessment=self.assessment,
            module=english_module,
            sort_order=1,
            max_score=Decimal("10.00"),
            counts_towards_ranking=False,
        )
        create_marking_score(
            self.ranking_assessment_module,
            self.participant_a,
            Decimal("20.00"),
        )
        create_marking_score(
            self.non_ranking_assessment_module,
            self.participant_a,
            Decimal("8.00"),
        )
        create_marking_score(
            self.ranking_assessment_module,
            self.participant_b,
            Decimal("22.00"),
        )
        create_marking_score(
            self.non_ranking_assessment_module,
            self.participant_b,
            Decimal("5.00"),
        )

    def test_score_table_context_uses_explicit_ranking_flag(self):
        context = build_assessment_score_table_context(self.assessment, "-total")
        rows = {row["user"].pk: row for row in context["table_rows"]}

        self.assertEqual(context["max_grand_total_score"], Decimal("35.00"))
        self.assertEqual(context["max_ranking_score"], Decimal("25.00"))
        self.assertEqual(rows[self.participant_a.pk]["total"], Decimal("28.00"))
        self.assertEqual(rows[self.participant_a.pk]["rank_score"], Decimal("20.00"))
        self.assertEqual(rows[self.participant_a.pk]["rank"], 2)
        self.assertEqual(rows[self.participant_b.pk]["total"], Decimal("27.00"))
        self.assertEqual(rows[self.participant_b.pk]["rank_score"], Decimal("22.00"))
        self.assertEqual(rows[self.participant_b.pk]["rank"], 1)

    def test_assessment_list_uses_explicit_ranking_flag_for_history_summary(self):
        self.client.force_login(self.participant_a)

        response = self.client.get(reverse("assessments:list"))

        self.assertEqual(response.status_code, 200)
        assessment = response.context["past_assessments"][0]
        self.assertEqual(assessment.my_grand_total_score, Decimal("28.00"))
        self.assertEqual(assessment.my_total_score, Decimal("20.00"))
        self.assertEqual(assessment.max_grand_total_score, Decimal("35.00"))
        self.assertEqual(assessment.max_ranking_score, Decimal("25.00"))
        self.assertEqual(assessment.my_rank, 2)
        self.assertContains(response, "(仅计入排名分的模块)")

    def test_assessment_list_selector_splits_sections_and_populates_history(self):
        context = build_assessment_list_context(self.participant_a, today=date(2026, 1, 20))

        self.assertFalse(context["show_management_actions"])
        self.assertEqual(len(context["current_assessments"]), 0)
        self.assertEqual(len(context["upcoming_assessments"]), 0)
        self.assertEqual(len(context["past_assessments"]), 1)
        assessment = context["past_assessments"][0]
        self.assertEqual(assessment.my_total_score, Decimal("20.00"))
        self.assertEqual(assessment.my_grand_total_score, Decimal("28.00"))

    def test_assessment_module_inherits_standard_module_ranking_default(self):
        interview_module = StandardModule.objects.create(
            project=self.training_cycle.project,
            code="ENG2",
            name="English Presentation",
            default_counts_towards_ranking=False,
        )
        followup_assessment = Assessment.objects.create(
            name="2026 排名规则复测",
            training_cycle=self.training_cycle,
            start_date=date(2026, 1, 12),
            end_date=date(2026, 1, 13),
        )

        assessment_module = AssessmentModule.objects.create(
            assessment=followup_assessment,
            module=interview_module,
            sort_order=0,
            max_score=Decimal("10.00"),
        )

        self.assertFalse(assessment_module.counts_towards_ranking)


class AssessmentCoachingWorkflowTests(TestCase):
    def setUp(self):
        self.coach_group = Group.objects.create(name=GROUP_COACH)
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )

        self.coach = User.objects.create_user(
            username="coach-a",
            password="testpass123",
            first_name="教练甲",
        )
        self.coach.groups.add(self.coach_group)

        self.other_coach = User.objects.create_user(
            username="coach-b",
            password="testpass123",
            first_name="教练乙",
        )
        self.other_coach.groups.add(self.coach_group)

        self.unassigned_coach = User.objects.create_user(
            username="coach-c",
            password="testpass123",
            first_name="教练丙",
        )
        self.unassigned_coach.groups.add(self.coach_group)

        self.participant_a = User.objects.create_user(
            username="student-a",
            password="testpass123",
            first_name="张三",
        )
        self.participant_b = User.objects.create_user(
            username="student-b",
            password="testpass123",
            first_name="李四",
        )

        competition_type = CompetitionType.objects.create(
            code="WSC",
            name="世界技能大赛",
        )
        project = Project.objects.create(
            competition_type=competition_type,
            code="ITSA",
            name="信息网络综合布线",
        )
        module_set = project.get_or_create_default_standard_module_set()
        self.training_cycle = TrainingCycle.objects.create(
            code="TC-WORKFLOW",
            name="流程测试周期",
            project=project,
            module_set=module_set,
            start_date=date(2026, 1, 1),
        )
        module_a = StandardModule.objects.create(project=project, code="A", name="模块 A")
        module_b = StandardModule.objects.create(project=project, code="B", name="模块 B")

        self.assessment = Assessment.objects.create(
            name="2026 夏季考核",
            training_cycle=self.training_cycle,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 2),
        )
        self.assessment.participants.set([self.participant_a, self.participant_b])

        self.assessment_module = AssessmentModule.objects.create(
            assessment=self.assessment,
            module=module_a,
            responsible_coach=self.coach,
            sort_order=0,
            max_score=Decimal("25.00"),
        )
        self.other_module = AssessmentModule.objects.create(
            assessment=self.assessment,
            module=module_b,
            responsible_coach=self.other_coach,
            sort_order=1,
            max_score=Decimal("25.00"),
        )

    def tearDown(self):
        for assessment_module in AssessmentModule.objects.all():
            for field_name in (
                "question_file",
                "scoring_standard_file",
                "scoring_sheet_file",
                "scoring_script_file",
            ):
                file_field = getattr(assessment_module, field_name)
                if file_field:
                    file_field.delete(save=False)

        for attachment in AssessmentAttachment.objects.all():
            if attachment.file:
                attachment.file.delete(save=False)

        super().tearDown()

    def _build_upload_file(self, name="sample.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4\nassessment test", content_type="application/pdf")

    def test_responsible_coach_can_view_assessment_detail(self):
        permission = Permission.objects.get(codename="add_markingschemeimport")
        self.coach.user_permissions.add(permission)
        self.client.force_login(self.coach)

        response = self.client.get(reverse("assessments:detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "考核资料")
        self.assertContains(response, "成绩管理")
        self.assertContains(response, "导入评分表")
        self.assertContains(response, "上传资料")
        self.assertContains(response, "锁定归档")
        self.assertContains(response, "锁定资料")
        self.assertContains(response, self.coach.display_name)

    def test_detail_page_shows_disabled_locked_buttons_without_unlock_actions(self):
        self.assessment_module.is_locked = True
        self.assessment_module.locked_by = self.admin_user
        self.assessment_module.is_material_locked = True
        self.assessment_module.material_locked_by = self.admin_user
        self.assessment_module.save(
            update_fields=[
                "is_locked",
                "locked_by",
                "is_material_locked",
                "material_locked_by",
            ]
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("assessments:detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "归档已锁定")
        self.assertContains(response, "资料已锁定")
        self.assertNotContains(response, "解锁成绩")
        self.assertNotContains(response, "解锁资料")

    def test_unassigned_coach_cannot_view_assessment_detail(self):
        self.client.force_login(self.unassigned_coach)

        response = self.client.get(reverse("assessments:detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 403)

    def test_responsible_coach_with_permission_gets_marking_import_link(self):
        permission = Permission.objects.get(codename="add_markingschemeimport")
        self.coach.user_permissions.add(permission)
        self.client.force_login(self.coach)

        response = self.client.get(reverse("assessments:detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"{reverse('marking:scheme_import')}?target_type=assessment_module&assessment_module={self.assessment_module.pk}",
        )

    def test_responsible_coach_can_lock_scores_from_detail_page(self):
        """负责教练可以在详情页锁定评分归档"""
        self.client.force_login(self.coach)
        url = reverse("assessments:module_score_lock", args=[self.assessment_module.pk])

        response = self.client.post(url, {
            "action": "lock",
        })

        self.assessment_module.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.assessment_module.is_locked)
        self.assertEqual(self.assessment_module.locked_by, self.coach)

    def test_locked_module_hides_marking_import_link(self):
        self.assessment_module.is_locked = True
        self.assessment_module.save(update_fields=["is_locked"])
        permission = Permission.objects.get(codename="add_markingschemeimport")
        self.coach.user_permissions.add(permission)
        self.client.force_login(self.coach)

        response = self.client.get(reverse("assessments:detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            f"{reverse('marking:scheme_import')}?target_type=assessment_module&amp;assessment_module={self.assessment_module.pk}",
        )

    def test_superuser_can_lock_and_unlock_scores_from_detail_page(self):
        """超管可以在详情页锁定并解锁成绩"""
        self.client.force_login(self.admin_user)
        url = reverse("assessments:module_score_lock", args=[self.assessment_module.pk])

        lock_response = self.client.post(url, {"action": "lock"})

        self.assessment_module.refresh_from_db()
        self.assertEqual(lock_response.status_code, 302)
        self.assertTrue(self.assessment_module.is_locked)
        self.assertEqual(self.assessment_module.locked_by, self.admin_user)

        unlock_response = self.client.post(url, {"action": "unlock"})

        self.assessment_module.refresh_from_db()
        self.assertEqual(unlock_response.status_code, 302)
        self.assertFalse(self.assessment_module.is_locked)

    def test_coach_cannot_unlock_locked_module_from_detail_page(self):
        """普通教练不能在详情页解锁成绩"""
        self.assessment_module.is_locked = True
        self.assessment_module.save(update_fields=["is_locked"])
        self.client.force_login(self.coach)
        url = reverse("assessments:module_score_lock", args=[self.assessment_module.pk])

        response = self.client.post(url, {"action": "unlock"})

        self.assertEqual(response.status_code, 403)
        self.assessment_module.refresh_from_db()
        self.assertTrue(self.assessment_module.is_locked)

    def test_responsible_coach_can_lock_materials_from_detail_page(self):
        self.client.force_login(self.coach)
        url = reverse("assessments:module_material_lock", args=[self.assessment_module.pk])

        response = self.client.post(url, {"action": "lock"})

        self.assessment_module.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.assessment_module.is_material_locked)
        self.assertEqual(self.assessment_module.material_locked_by, self.coach)

    def test_superuser_can_lock_and_unlock_materials_from_detail_page(self):
        self.client.force_login(self.admin_user)
        url = reverse("assessments:module_material_lock", args=[self.assessment_module.pk])

        lock_response = self.client.post(url, {"action": "lock"})

        self.assessment_module.refresh_from_db()
        self.assertEqual(lock_response.status_code, 302)
        self.assertTrue(self.assessment_module.is_material_locked)
        self.assertEqual(self.assessment_module.material_locked_by, self.admin_user)

        unlock_response = self.client.post(url, {"action": "unlock"})

        self.assessment_module.refresh_from_db()
        self.assertEqual(unlock_response.status_code, 302)
        self.assertFalse(self.assessment_module.is_material_locked)

    def test_other_coach_cannot_upload_files_for_unassigned_module(self):
        self.client.force_login(self.other_coach)

        response = self.client.get(
            reverse("assessments:file_upload", args=[self.assessment_module.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_file_upload_page_is_read_only_when_materials_locked(self):
        self.assessment_module.is_material_locked = True
        self.assessment_module.save(update_fields=["is_material_locked"])
        self.client.force_login(self.coach)

        response = self.client.get(
            reverse("assessments:file_upload", args=[self.assessment_module.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "只读模式")
        self.assertNotContains(response, "添加试题附件")
        self.assertNotIn('<button type="submit"', response.content.decode())

    def test_file_upload_page_places_question_attachments_after_question_file(self):
        self.client.force_login(self.coach)

        response = self.client.get(
            reverse("assessments:file_upload", args=[self.assessment_module.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "添加试题附件")
        content = response.content.decode()
        self.assertLess(content.index("试题文件"), content.index("添加试题附件"))
        self.assertLess(content.index("添加试题附件"), content.index("评分标准文件"))

    def test_question_attachment_upload_path_uses_dedicated_subdirectory(self):
        attachment = AssessmentAttachment.objects.create(
            assessment_module=self.assessment_module,
            file=self._build_upload_file("attachment-subdir.pdf"),
        )

        self.assertIn("/试题附件/", attachment.file.name)
        self.assertTrue(attachment.file.name.endswith("/试题附件/attachment-subdir.pdf"))

    def test_uploaded_materials_use_assessments_storage_root(self):
        attachment = AssessmentAttachment.objects.create(
            assessment_module=self.assessment_module,
            file=self._build_upload_file("attachment-root.pdf"),
        )

        self.assertIn(
            str(Path("media-private") / "assessments"),
            attachment.file.path,
        )

    def test_material_lock_rejects_file_upload(self):
        self.assessment_module.is_material_locked = True
        self.assessment_module.save(update_fields=["is_material_locked"])
        self.client.force_login(self.coach)

        response = self.client.post(
            reverse("assessments:file_upload", args=[self.assessment_module.pk]),
            {"question_file": self._build_upload_file("question.pdf")},
        )

        self.assertEqual(response.status_code, 403)
        self.assessment_module.refresh_from_db()
        self.assertFalse(bool(self.assessment_module.question_file))

    def test_past_assessment_still_allows_material_upload_when_unlocked(self):
        self.assessment.end_date = date(2026, 4, 1)
        self.assessment.save(update_fields=["end_date"])
        self.client.force_login(self.coach)

        response = self.client.post(
            reverse("assessments:file_upload", args=[self.assessment_module.pk]),
            {"question_file": self._build_upload_file("question.pdf")},
        )

        self.assertEqual(response.status_code, 302)
        self.assessment_module.refresh_from_db()
        self.assertTrue(bool(self.assessment_module.question_file))

    def test_file_upload_accepts_multiple_question_attachments(self):
        self.client.force_login(self.coach)

        response = self.client.post(
            reverse("assessments:file_upload", args=[self.assessment_module.pk]),
            {
                "attachments": [
                    self._build_upload_file("attachment-1.pdf"),
                    self._build_upload_file("attachment-2.pdf"),
                ],
            },
        )

        self.assertEqual(response.status_code, 302)
        attachments = list(self.assessment_module.attachments.order_by("file"))
        self.assertEqual(len(attachments), 2)
        for attachment in attachments:
            self.assertIn("/试题附件/", attachment.file.name)
            self.assertTrue(attachment.file.name.endswith(".pdf"))

    def test_material_lock_rejects_module_file_deletion(self):
        self.assessment_module.question_file = self._build_upload_file("question.pdf")
        self.assessment_module.save(update_fields=["question_file"])
        self.assessment_module.is_material_locked = True
        self.assessment_module.save(update_fields=["is_material_locked"])
        self.client.force_login(self.coach)

        response = self.client.delete(
            reverse(
                "assessments:delete_module_file",
                args=[self.assessment_module.pk, "question_file"],
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assessment_module.refresh_from_db()
        self.assertTrue(bool(self.assessment_module.question_file))

    def test_htmx_module_file_deletion_rerenders_upload_using_form_field_config(self):
        self.assessment_module.question_file = self._build_upload_file("question.pdf")
        self.assessment_module.save(update_fields=["question_file"])
        self.client.force_login(self.coach)

        response = self.client.delete(
            reverse(
                "assessments:delete_module_file",
                args=[self.assessment_module.pk, "question_file"],
            ),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assessment_module.refresh_from_db()
        self.assertFalse(bool(self.assessment_module.question_file))
        self.assertContains(response, 'id="file-display-question_file"')
        self.assertContains(response, 'name="question_file"')
        self.assertContains(response, f'accept="{ASSESSMENT_TP_UPLOAD_SPEC.accept}"')
        self.assertContains(
            response,
            ASSESSMENT_TP_UPLOAD_SPEC.help_text("上传试题文件"),
        )

    def test_material_lock_rejects_attachment_deletion(self):
        attachment = AssessmentAttachment.objects.create(
            assessment_module=self.assessment_module,
            file=self._build_upload_file("attachment.pdf"),
        )
        self.assessment_module.is_material_locked = True
        self.assessment_module.save(update_fields=["is_material_locked"])
        self.client.force_login(self.coach)

        response = self.client.delete(
            reverse("assessments:delete_attachment", args=[attachment.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(AssessmentAttachment.objects.filter(pk=attachment.pk).exists())


class AssessmentAdminSortOrderTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        competition_type = CompetitionType.objects.create(
            code="WSC",
            name="世界技能大赛",
        )
        project = Project.objects.create(
            competition_type=competition_type,
            code="ITSA",
            name="信息网络综合布线",
        )
        module_set = project.get_or_create_default_standard_module_set()
        self.training_cycle = TrainingCycle.objects.create(
            code="TC-SORT",
            name="排序后台周期",
            project=project,
            module_set=module_set,
            start_date=date(2026, 1, 1),
        )
        self.assessment = Assessment.objects.create(
            name="2026 秋季考核",
            training_cycle=self.training_cycle,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
        )
        module_a = StandardModule.objects.create(project=project, code="A", name="模块 A")
        module_b = StandardModule.objects.create(project=project, code="B", name="模块 B")
        self.assessment_module_a = AssessmentModule.objects.create(
            assessment=self.assessment,
            module=module_a,
            sort_order=0,
        )
        self.assessment_module_b = AssessmentModule.objects.create(
            assessment=self.assessment,
            module=module_b,
            sort_order=1,
        )

    def test_assessment_module_admin_changelist_supports_inline_sort_order_editing(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:assessments_assessmentmodule_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['cl'].formset)
        self.assertIn('sort_order', response.context['cl'].formset.forms[0].fields)

    def test_assessment_admin_inline_prefills_next_sort_order(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:assessments_assessment_change", args=[self.assessment.pk])
        )

        self.assertEqual(response.status_code, 200)
        inline_formset = response.context['inline_admin_formsets'][0].formset
        self.assertEqual(len(inline_formset.extra_forms), 0)
        self.assertEqual(inline_formset.empty_form.initial['sort_order'], 2)

    def test_assessment_module_add_view_prefills_next_sort_order_for_selected_assessment(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:assessments_assessmentmodule_add"),
            {"assessment": self.assessment.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['adminform'].form.initial['assessment'], self.assessment.pk)
        self.assertEqual(response.context['adminform'].form.initial['sort_order'], 2)

    def test_assessment_module_add_view_exposes_ranking_default_sync_metadata(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:assessments_assessmentmodule_add"),
            {"assessment": self.assessment.pk},
        )

        self.assertEqual(response.status_code, 200)
        form = response.context['adminform'].form
        self.assertEqual(
            form.fields['module'].widget.attrs['data-ranking-default-url'],
            reverse('admin:assessments_assessmentmodule_module_ranking_default'),
        )
        self.assertEqual(
            form.fields['counts_towards_ranking'].widget.attrs['data-follow-module-default'],
            'true',
        )
        self.assertContains(response, 'assessments/js/assessment_module_admin.js')

    def test_assessment_admin_inline_empty_form_exposes_ranking_default_sync_metadata(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:assessments_assessment_change", args=[self.assessment.pk])
        )

        self.assertEqual(response.status_code, 200)
        inline_formset = response.context['inline_admin_formsets'][0].formset
        self.assertEqual(
            inline_formset.empty_form.fields['module'].widget.attrs['data-ranking-default-url'],
            reverse('admin:assessments_assessmentmodule_module_ranking_default'),
        )
        self.assertEqual(
            inline_formset.empty_form.fields['counts_towards_ranking'].widget.attrs['data-follow-module-default'],
            'true',
        )

    def test_assessment_module_ranking_default_endpoint_returns_standard_module_default(self):
        module_c = StandardModule.objects.create(
            project=self.training_cycle.project,
            code="ENG",
            name="English 口语",
            default_counts_towards_ranking=False,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('admin:assessments_assessmentmodule_module_ranking_default'),
            {'module_id': module_c.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                'found': True,
                'module': {
                    'id': module_c.pk,
                    'label': str(module_c),
                    'default_counts_towards_ranking': False,
                },
            },
        )

    def test_assessment_module_change_view_keeps_file_fields_and_attachment_inline(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:assessments_assessmentmodule_change", args=[self.assessment_module_a.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['inline_admin_formsets'][0].opts.model,
            AssessmentAttachment,
        )
        form = response.context['adminform'].form
        self.assertIn('question_file', form.fields)
        self.assertIn('scoring_standard_file', form.fields)
        self.assertIn('scoring_sheet_file', form.fields)
        self.assertIn('scoring_script_file', form.fields)
        self.assertIn('counts_towards_ranking', form.fields)
        self.assertEqual(
            form.fields['counts_towards_ranking'].widget.attrs['data-follow-module-default'],
            'false',
        )
        field_names = list(form.fields)
        self.assertLess(field_names.index('question_file'), field_names.index('scoring_standard_file'))
        self.assertLess(field_names.index('question_file'), field_names.index('scoring_sheet_file'))
        self.assertLess(field_names.index('question_file'), field_names.index('scoring_script_file'))

        attachment_inline = next(
            (
                inline_formset
                for inline_formset in response.context['inline_admin_formsets']
                if inline_formset.opts.model == AssessmentAttachment
            ),
            None,
        )
        self.assertIsNotNone(attachment_inline)
        self.assertEqual(attachment_inline.opts.verbose_name, '试题附件')
        self.assertEqual(attachment_inline.opts.verbose_name_plural, '试题附件')
        self.assertIn('file', attachment_inline.formset.empty_form.fields)
        self.assertIn('description', attachment_inline.formset.empty_form.fields)

    def test_assessment_module_add_view_inherits_standard_module_default_ranking_rule(self):
        module_c = StandardModule.objects.create(
            project=self.training_cycle.project,
            code="ENG",
            name="English 口语",
            default_counts_towards_ranking=False,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("admin:assessments_assessmentmodule_add"),
            {
                'assessment': str(self.assessment.pk),
                'module': str(module_c.pk),
                'responsible_coach': '',
                'sort_order': '2',
                'max_score': '25.00',
                'duration': '0.0',
                'counts_towards_ranking': 'on',
                'attachments-TOTAL_FORMS': '1',
                'attachments-INITIAL_FORMS': '0',
                'attachments-MIN_NUM_FORMS': '0',
                'attachments-MAX_NUM_FORMS': '1000',
                '_save': '保存',
            },
        )

        self.assertEqual(response.status_code, 302)
        created_module = AssessmentModule.objects.get(
            assessment=self.assessment,
            module=module_c,
        )
        self.assertFalse(created_module.counts_towards_ranking)

    def test_assessment_attachment_is_not_registered_as_standalone_admin_model(self):
        self.assertNotIn(AssessmentAttachment, admin.site._registry)


class AssessmentCutoverCommandTests(TestCase):
    def test_cutover_command_is_noop_for_current_state(self):
        output = StringIO()
        media_root = Path(settings.BASE_DIR) / ".assessment-cutover-test-media"
        upload_root = media_root / "assessments"
        shutil.rmtree(media_root, ignore_errors=True)
        upload_root.mkdir(parents=True)
        try:
            with patch(
                "core.management.commands.cutover_assessment_to_assessments.ASSESSMENT_UPLOAD_DIR",
                upload_root,
            ):
                call_command("cutover_assessment_to_assessments", stdout=output)
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

        self.assertIn("无需切换", output.getvalue())


class AssessmentMigrationRepairTests(TransactionTestCase):
    def test_score_removal_migration_nulls_orphan_admin_log_content_types(self):
        user = User.objects.create_superuser(
            username="admin-log-repair",
            password="testpass123",
            email="admin-log-repair@example.com",
        )
        entry = LogEntry.objects.create(
            action_time=timezone.now(),
            user=user,
            content_type=None,
            object_id="broken",
            object_repr="Broken content type",
            action_flag=ADDITION,
            change_message="",
        )
        missing_content_type_id = 987654
        connection.disable_constraint_checking()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE django_admin_log SET content_type_id = %s WHERE id = %s",
                    [missing_content_type_id, entry.pk],
                )
        finally:
            connection.enable_constraint_checking()

        migration = importlib.import_module(
            "assessments.migrations.0007_remove_score_uniq_score_assessmentmodule_user_and_more"
        )
        with connection.schema_editor() as schema_editor:
            migration.clear_orphan_admin_log_content_types(None, schema_editor)

        entry.refresh_from_db()
        self.assertIsNone(entry.content_type_id)


class AssessmentCutoverRecoveryTests(TransactionTestCase):
    def test_cutover_command_recovers_dual_table_state_when_new_table_is_empty(self):
        competition_type = CompetitionType.objects.create(
            code="WSC-CUTOVER",
            name="切换测试赛事",
        )
        project = Project.objects.create(
            competition_type=competition_type,
            code="CUTOVER",
            name="切换测试项目",
        )
        training_cycle = TrainingCycle.objects.create(
            code="TC-CUTOVER",
            name="切换测试周期",
            project=project,
            module_set=project.get_or_create_default_standard_module_set(),
            start_date=date(2026, 1, 1),
        )
        assessment = Assessment.objects.create(
            name="2026 夏季考核",
            training_cycle=training_cycle,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
        )
        MigrationRecorder.Migration.objects.create(app="assessment", name="0001_initial")
        old_content_type = ContentType.objects.create(app_label="assessment", model="assessment")
        Permission.objects.create(
            name="旧考核查看权限",
            codename="view_assessment_legacy",
            content_type=old_content_type,
        )

        self.addCleanup(
            lambda: connection.cursor().execute("DROP TABLE IF EXISTS assessment_assessment")
        )
        self.addCleanup(
            lambda: connection.cursor().execute("DROP TABLE IF EXISTS assessments_assessment_empty_backup")
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = %s",
                ["assessments_assessment"],
            )
            create_sql = cursor.fetchone()[0].replace(
                '"assessments_assessment"',
                '"assessment_assessment"',
                1,
            )
            cursor.execute(create_sql)
            cursor.execute("INSERT INTO assessment_assessment SELECT * FROM assessments_assessment")
            cursor.execute("DELETE FROM assessments_assessment")

        output = StringIO()
        call_command("cutover_assessment_to_assessments", "--execute", stdout=output)

        self.assertIn("assessment 已切换为 assessments", output.getvalue())
        self.assertEqual(Assessment.objects.count(), 1)
        self.assertEqual(Assessment.objects.get().pk, assessment.pk)
        self.assertFalse(MigrationRecorder.Migration.objects.filter(app="assessment").exists())
        self.assertFalse(ContentType.objects.filter(app_label="assessment", model="assessment").exists())
        self.assertTrue(
            Permission.objects.filter(
                codename="view_assessment_legacy",
                content_type__app_label="assessments",
            ).exists()
        )
