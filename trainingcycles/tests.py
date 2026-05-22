from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition, CompetitionProject, CompetitionTrainingCycleTarget
from competition_standards.models import CompetitionType, Project, TrainingCycle


User = get_user_model()


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


class TrainingCycleAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='trainingcycle-admin',
            password='testpass123',
            email='trainingcycle-admin@example.com',
        )
        self.competition_type = CompetitionType.objects.create(code='WSC-ADMIN', name='后台测试赛事')
        self.project = Project.objects.create(
            competition_type=self.competition_type,
            code='ITNSA',
            name='网络系统管理',
        )
        self.module_set = self.project.get_or_create_default_standard_module_set()
        TrainingCycle.objects.create(
            code='TC-ADMIN',
            name='后台列表周期',
            project=self.project,
            module_set=self.module_set,
            start_date=date(2026, 1, 1),
        )

    def test_changelist_handles_project_with_missing_competition_type_relation(self):
        self.client.force_login(self.admin_user)

        with connection.constraint_checks_disabled():
            Project.objects.filter(pk=self.project.pk).update(competition_type_id=self.competition_type.pk + 9999)
            response = self.client.get(reverse('admin:curriculum_trainingcycle_changelist'))
            Project.objects.filter(pk=self.project.pk).update(competition_type_id=self.competition_type.pk)

        connection.check_constraints()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '未分配赛事类型 / 网络系统管理 (ITNSA)')

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

        cycle = TrainingCycle.objects.create(
            code='TC-TARGET',
            name='目标错误周期',
            project=self.project,
            module_set=self.module_set,
            start_date=date(2026, 1, 1),
        )

        target = CompetitionTrainingCycleTarget(
            training_cycle=cycle,
            competition_project=other_competition_project,
            kind=CompetitionTrainingCycleTarget.Kind.PRIMARY,
        )

        with self.assertRaises(ValidationError):
            target.full_clean()
