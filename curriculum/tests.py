from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CompetitionType, Project, StandardModule


User = get_user_model()


class ProjectCompetitionTypeTests(TestCase):
    def test_project_code_is_unique_within_competition_type(self):
        competition_type = CompetitionType.objects.create(code='WSC', name='世界技能大赛')
        Project.objects.create(
            competition_type=competition_type,
            code='ITNSA',
            name='网络系统管理',
        )

        duplicate_project = Project(
            competition_type=competition_type,
            code='ITNSA',
            name='重复项目',
        )

        with self.assertRaises(ValidationError):
            duplicate_project.full_clean()

    def test_project_code_can_repeat_across_competition_types(self):
        worldskills = CompetitionType.objects.create(code='WSC', name='世界技能大赛')
        national = CompetitionType.objects.create(code='NSC', name='全国技能大赛')

        first_project = Project.objects.create(
            competition_type=worldskills,
            code='ITNSA',
            name='网络系统管理',
        )
        second_project = Project.objects.create(
            competition_type=national,
            code='ITNSA',
            name='网络系统管理',
        )

        self.assertEqual(first_project.code, second_project.code)
        self.assertNotEqual(first_project.pk, second_project.pk)

    def test_project_str_falls_back_when_competition_type_missing(self):
        project = Project(code='LEGACY', name='遗留项目')

        self.assertEqual(str(project), '未分配赛事类型 / 遗留项目 (LEGACY)')


class StandardModuleRankingDefaultTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='curriculum-admin',
            password='testpass123',
            email='curriculum@example.com',
        )
        competition_type = CompetitionType.objects.create(code='WSC-CUR', name='课程测试赛事')
        self.project = Project.objects.create(
            competition_type=competition_type,
            code='CUR',
            name='课程测试项目',
        )
        self.module = StandardModule.objects.create(
            project=self.project,
            code='ENG',
            name='English Interview',
            default_counts_towards_ranking=False,
        )

    def test_standard_module_persists_default_ranking_flag(self):
        self.assertFalse(self.module.default_counts_towards_ranking)

    def test_standard_module_admin_exposes_default_ranking_flag(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('admin:curriculum_standardmodule_change', args=[self.module.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('default_counts_towards_ranking', response.context['adminform'].form.fields)

