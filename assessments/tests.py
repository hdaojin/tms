from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse

from competitions.models import CompetitionType, Project, StandardModule, StandardModuleSet
from core.constants import GROUP_COACH

from .models import Assessment, AssessmentAttachment, AssessmentModule, Score


User = get_user_model()


class AssessmentModuleOrderingTests(TestCase):
    def setUp(self):
        competition_type = CompetitionType.objects.create(
            code="WSC",
            name="世界技能大赛",
        )
        project = Project.objects.create(
            code="ITNSA",
            name="信息网络布线",
        )
        self.assessment = Assessment.objects.create(
            name="2026 春季考核",
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
        self.request = RequestFactory().get("/admin/assessments/assessmentmodule/add/")
        self.admin = admin.site._registry[AssessmentModule]

    def test_admin_module_field_only_shows_current_modules(self):
        field = AssessmentModule._meta.get_field("module")

        form_field = self.admin.formfield_for_foreignkey(field, self.request)

        self.assertEqual(list(form_field.queryset), [self.current_module])


class AssessmentsUrlTests(TestCase):
    def test_assessment_list_is_mounted_at_app_root(self):
        self.assertEqual(reverse("assessments:list"), "/assessments/")


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
            code="ITSA",
            name="信息网络综合布线",
        )
        module_a = StandardModule.objects.create(project=project, code="A", name="模块 A")
        module_b = StandardModule.objects.create(project=project, code="B", name="模块 B")

        self.assessment = Assessment.objects.create(
            name="2026 夏季考核",
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
        self.client.force_login(self.coach)

        response = self.client.get(reverse("assessments:detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "考核资料")
        self.assertContains(response, "成绩管理")
        self.assertContains(response, "录入成绩")
        self.assertContains(response, "上传资料")
        self.assertContains(response, "锁定成绩")
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
        self.assertContains(response, "成绩已锁定")
        self.assertContains(response, "资料已锁定")
        self.assertNotContains(response, "解锁成绩")
        self.assertNotContains(response, "解锁资料")

    def test_unassigned_coach_cannot_view_assessment_detail(self):
        self.client.force_login(self.unassigned_coach)

        response = self.client.get(reverse("assessments:detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 403)

    def test_responsible_coach_can_submit_batch_scores(self):
        """负责教练可以批量录入成绩"""
        self.client.force_login(self.coach)
        url = reverse("assessments:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.post(url, {
            f"score_{self.participant_a.pk}": "18.50",
            f"remarks_{self.participant_a.pk}": "发挥稳定",
            f"score_{self.participant_b.pk}": "20.00",
            f"remarks_{self.participant_b.pk}": "注意细节",
        })

        self.assertEqual(response.status_code, 302)
        participant_a_score = Score.objects.get(
            assessment_module=self.assessment_module,
            user=self.participant_a,
        )
        participant_b_score = Score.objects.get(
            assessment_module=self.assessment_module,
            user=self.participant_b,
        )
        self.assertEqual(participant_a_score.score, Decimal("18.50"))
        self.assertEqual(participant_a_score.remarks, "发挥稳定")
        self.assertEqual(participant_b_score.score, Decimal("20.00"))
        self.assertEqual(participant_b_score.remarks, "注意细节")

    def test_responsible_coach_can_lock_scores_from_detail_page(self):
        """负责教练可以在详情页锁定成绩"""
        self.client.force_login(self.coach)
        url = reverse("assessments:module_score_lock", args=[self.assessment_module.pk])

        response = self.client.post(url, {
            "action": "lock",
        })

        self.assessment_module.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.assessment_module.is_locked)
        self.assertEqual(self.assessment_module.locked_by, self.coach)

    def test_locked_module_rejects_score_submission(self):
        """已锁定模块拒绝成绩提交"""
        self.assessment_module.is_locked = True
        self.assessment_module.save(update_fields=["is_locked"])
        self.client.force_login(self.coach)
        url = reverse("assessments:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.post(url, {
            "action": "save",
            f"score_{self.participant_a.pk}": "10.00",
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Score.objects.filter(assessment_module=self.assessment_module).exists()
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

    def test_unassigned_coach_cannot_access_module_score_entry(self):
        """非负责教练无法访问成绩录入页面"""
        self.client.force_login(self.unassigned_coach)
        url = reverse("assessments:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_module_score_entry_page_accessible_by_responsible_coach(self):
        """负责教练可以访问成绩录入页面"""
        self.client.force_login(self.coach)
        url = reverse("assessments:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.participant_a.display_name)
        self.assertContains(response, self.participant_b.display_name)
        self.assertContains(response, "备注")
        self.assertContains(response, "重置")
        self.assertNotContains(response, "保存并锁定")
        self.assertNotContains(response, "成绩锁定请返回考核详情页统一操作。")

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
        self.assertNotContains(response, "提交")

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
            code="ITSA",
            name="信息网络综合布线",
        )
        self.assessment = Assessment.objects.create(
            name="2026 秋季考核",
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
        self.assertEqual(response.context['inline_admin_formsets'][1].opts.model, Score)
        form = response.context['adminform'].form
        self.assertIn('question_file', form.fields)
        self.assertIn('scoring_standard_file', form.fields)
        self.assertIn('scoring_sheet_file', form.fields)
        self.assertIn('scoring_script_file', form.fields)
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

    def test_assessment_attachment_is_not_registered_as_standalone_admin_model(self):
        self.assertNotIn(AssessmentAttachment, admin.site._registry)


class AssessmentCutoverCommandTests(TestCase):
    def test_cutover_command_is_noop_for_current_state(self):
        output = StringIO()

        with TemporaryDirectory() as temp_dir:
            upload_root = Path(temp_dir) / "assessments"
            upload_root.mkdir()
            with patch(
                "core.management.commands.cutover_assessment_to_assessments.ASSESSMENT_UPLOAD_DIR",
                upload_root,
            ):
                call_command("cutover_assessment_to_assessments", stdout=output)

        self.assertIn("无需切换", output.getvalue())


class AssessmentCutoverRecoveryTests(TransactionTestCase):
    def test_cutover_command_recovers_dual_table_state_when_new_table_is_empty(self):
        assessment = Assessment.objects.create(
            name="2026 夏季考核",
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
