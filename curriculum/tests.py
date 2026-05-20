from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import CompetitionType, Project


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

