from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from competitions.models import CompetitionType, Module, Project
from core.constants import GROUP_COACH

from .models import Assessment, AssessmentModule, Score


User = get_user_model()


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
        self.assessment = Assessment.objects.create(
            name="2026 春季考核",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 2),
        )

        module_b = Module.objects.create(project=project, code="B", name="模块 B")
        module_a = Module.objects.create(project=project, code="A", name="模块 A")
        module_c = Module.objects.create(project=project, code="C", name="模块 C")

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


class AssessmentCoachingWorkflowTests(TestCase):
    def setUp(self):
        self.coach_group = Group.objects.create(name=GROUP_COACH)

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
        module_a = Module.objects.create(project=project, code="A", name="模块 A")
        module_b = Module.objects.create(project=project, code="B", name="模块 B")

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

    def test_responsible_coach_can_view_assessment_detail(self):
        self.client.force_login(self.coach)

        response = self.client.get(reverse("assessment:detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "录入成绩")
        self.assertContains(response, self.coach.display_name)

    def test_unassigned_coach_cannot_view_assessment_detail(self):
        self.client.force_login(self.unassigned_coach)

        response = self.client.get(reverse("assessment:detail", args=[self.assessment.pk]))

        self.assertEqual(response.status_code, 403)

    def test_responsible_coach_can_submit_batch_scores(self):
        """负责教练可以批量录入成绩"""
        self.client.force_login(self.coach)
        url = reverse("assessment:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.post(url, {
            "action": "save",
            f"score_{self.participant_a.pk}": "18.50",
            f"score_{self.participant_b.pk}": "20.00",
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Score.objects.get(
                assessment_module=self.assessment_module,
                user=self.participant_a,
            ).score,
            Decimal("18.50"),
        )
        self.assertEqual(
            Score.objects.get(
                assessment_module=self.assessment_module,
                user=self.participant_b,
            ).score,
            Decimal("20.00"),
        )

    def test_responsible_coach_can_save_and_lock_module(self):
        """负责教练可以保存并锁定模块成绩"""
        self.client.force_login(self.coach)
        url = reverse("assessment:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.post(url, {
            "action": "lock",
            f"score_{self.participant_a.pk}": "22.00",
        })

        self.assessment_module.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.assessment_module.is_locked)
        self.assertEqual(self.assessment_module.locked_by, self.coach)
        self.assertTrue(
            Score.objects.filter(
                assessment_module=self.assessment_module,
                user=self.participant_a,
                score=Decimal("22.00"),
            ).exists()
        )

    def test_locked_module_rejects_score_submission(self):
        """已锁定模块拒绝成绩提交"""
        self.assessment_module.is_locked = True
        self.assessment_module.save(update_fields=["is_locked"])
        self.client.force_login(self.coach)
        url = reverse("assessment:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.post(url, {
            "action": "save",
            f"score_{self.participant_a.pk}": "10.00",
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Score.objects.filter(assessment_module=self.assessment_module).exists()
        )

    def test_superuser_can_unlock_locked_module(self):
        """超管可以解锁已锁定模块"""
        self.assessment_module.is_locked = True
        self.assessment_module.save(update_fields=["is_locked"])
        admin_user = User.objects.create_superuser(
            username="admin", password="testpass123"
        )
        self.client.force_login(admin_user)
        url = reverse("assessment:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.post(url, {"action": "unlock"})

        self.assessment_module.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.assessment_module.is_locked)

    def test_coach_cannot_unlock_locked_module(self):
        """普通教练无法解锁模块"""
        self.assessment_module.is_locked = True
        self.assessment_module.save(update_fields=["is_locked"])
        self.client.force_login(self.coach)
        url = reverse("assessment:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.post(url, {"action": "unlock"})

        self.assertEqual(response.status_code, 403)
        self.assessment_module.refresh_from_db()
        self.assertTrue(self.assessment_module.is_locked)

    def test_unassigned_coach_cannot_access_module_score_entry(self):
        """非负责教练无法访问成绩录入页面"""
        self.client.force_login(self.unassigned_coach)
        url = reverse("assessment:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_module_score_entry_page_accessible_by_responsible_coach(self):
        """负责教练可以访问成绩录入页面"""
        self.client.force_login(self.coach)
        url = reverse("assessment:module_score_entry", args=[self.assessment_module.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.participant_a.display_name)
        self.assertContains(response, self.participant_b.display_name)

    def test_other_coach_cannot_upload_files_for_unassigned_module(self):
        self.client.force_login(self.other_coach)

        response = self.client.get(
            reverse("assessment:file_upload", args=[self.assessment_module.pk])
        )

        self.assertEqual(response.status_code, 403)


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
        self.assessment = Assessment.objects.create(
            name="2026 秋季考核",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
        )
        module_a = Module.objects.create(project=project, code="A", name="模块 A")
        module_b = Module.objects.create(project=project, code="B", name="模块 B")
        AssessmentModule.objects.create(
            assessment=self.assessment,
            module=module_a,
            sort_order=0,
        )
        AssessmentModule.objects.create(
            assessment=self.assessment,
            module=module_b,
            sort_order=1,
        )

    def test_assessment_module_admin_changelist_supports_inline_sort_order_editing(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:assessment_assessmentmodule_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['cl'].formset)
        self.assertIn('sort_order', response.context['cl'].formset.forms[0].fields)

    def test_assessment_admin_inline_prefills_next_sort_order(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:assessment_assessment_change", args=[self.assessment.pk])
        )

        self.assertEqual(response.status_code, 200)
        inline_formset = response.context['inline_admin_formsets'][0].formset
        self.assertEqual(inline_formset.empty_form.initial['sort_order'], 2)

    def test_assessment_module_add_view_prefills_next_sort_order_for_selected_assessment(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:assessment_assessmentmodule_add"),
            {"assessment": self.assessment.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['adminform'].form.initial['assessment'], self.assessment.pk)
        self.assertEqual(response.context['adminform'].form.initial['sort_order'], 2)
