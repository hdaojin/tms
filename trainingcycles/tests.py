from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from competitions.models import Competition, CompetitionProject
from curriculum.models import CompetitionType, Project

from .models import TrainingCycle


class TrainingCycleValidationTests(TestCase):
    def setUp(self):
        self.competition_type = CompetitionType.objects.create(code='WSC', name='世界技能大赛')
        self.project = Project.objects.create(
            competition_type=self.competition_type,
            code='ITNSA',
            name='网络系统管理',
        )
        self.module_set = self.project.get_or_create_default_standard_module_set()

    def test_module_set_must_belong_to_project(self):
        other_project = Project.objects.create(
            competition_type=self.competition_type,
            code='CLOUD',
            name='云计算',
        )
        other_module_set = other_project.get_or_create_default_standard_module_set()

        cycle = TrainingCycle(
            code='TC-MISMATCH',
            name='错误周期',
            project=self.project,
            module_set=other_module_set,
            start_date=date(2026, 1, 1),
        )

        with self.assertRaises(ValidationError):
            cycle.full_clean()

    def test_target_competition_project_must_belong_to_project(self):
        other_project = Project.objects.create(
            competition_type=self.competition_type,
            code='CLOUD',
            name='云计算',
        )
        competition = Competition.objects.create(
            competition_type=self.competition_type,
            name='第48届世界技能大赛',
            code='WSC2026',
        )
        other_competition_project = CompetitionProject.objects.create(
            competition=competition,
            project=other_project,
        )

        cycle = TrainingCycle(
            code='TC-TARGET',
            name='目标错误周期',
            project=self.project,
            module_set=self.module_set,
            primary_competition_project=other_competition_project,
            start_date=date(2026, 1, 1),
        )

        with self.assertRaises(ValidationError):
            cycle.full_clean()
