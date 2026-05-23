from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from competitions.models import Competition, CompetitionProject, CompetitionTrainingCycleTarget

from .models import CompetitionType, Project, StandardModule, StandardModuleSet, TrainingCycle


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
            username='competition-standards-admin',
            password='testpass123',
            email='competition-standards@example.com',
        )
        competition_type = CompetitionType.objects.create(code='WSC-CUR', name='课程测试赛事')
        self.project = Project.objects.create(
            competition_type=competition_type,
            code='CUR',
            name='课程测试项目',
        )
        self.module_set = self.project.get_or_create_default_standard_module_set()
        self.module = StandardModule.objects.create(
            project=self.project,
            module_set=self.module_set,
            code='ENG',
            name='English Interview',
            default_counts_towards_ranking=False,
        )

    def test_standard_module_persists_default_ranking_flag(self):
        self.assertFalse(self.module.default_counts_towards_ranking)

    def test_standard_module_admin_exposes_default_ranking_flag(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse('admin:competition_standards_standardmodule_change', args=[self.module.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('default_counts_towards_ranking', response.context['adminform'].form.fields)


class ProjectAdminDanglingCompetitionTypeTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='competition-standards-project-admin',
            password='testpass123',
            email='competition-standards-project@example.com',
        )
        self.client.force_login(self.admin_user)
        competition_type = CompetitionType.objects.create(code='BROKEN-CT', name='损坏赛事类型')
        self.project = Project.objects.create(
            competition_type=competition_type,
            code='BROKEN-PROJECT',
            name='损坏项目',
        )
        self.valid_competition_type_id = competition_type.pk
        self.addCleanup(self._restore_project_competition_type)

    def _set_project_competition_type(self, competition_type_id):
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = OFF')
            cursor.execute(
                f'UPDATE {Project._meta.db_table} SET competition_type_id = %s WHERE id = %s',
                [competition_type_id, self.project.pk],
            )
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = ON')

    def _restore_project_competition_type(self):
        self._set_project_competition_type(self.valid_competition_type_id)

    def _break_project_competition_type(self, broken_competition_type_id=999999):
        self._set_project_competition_type(broken_competition_type_id)

    def test_project_admin_changelist_shows_rows_with_dangling_competition_type(self):
        self._break_project_competition_type()

        response = self.client.get(reverse('admin:competition_standards_project_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '损坏项目')
        self.assertContains(response, '缺失赛事类型（ID: 999999）')
        self.assertContains(response, reverse('admin:competition_standards_project_change', args=[self.project.pk]))


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
            response = self.client.get(reverse('admin:competition_standards_trainingcycle_changelist'))
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


class CutoverCompetitionStandardsSafetyTests(TestCase):
    def test_cutover_blocks_when_target_table_already_has_data(self):
        CompetitionType.objects.create(code='CURRENT', name='当前目标表数据')
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE curriculum_competitiontype (id integer PRIMARY KEY)')
        self.addCleanup(self._drop_legacy_table)

        output = StringIO()
        with self.assertRaisesMessage(CommandError, '目标表已有数据'):
            call_command('cutover_competition_standards', '--execute', stdout=output)

    def _drop_legacy_table(self):
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS curriculum_competitiontype')


class CutoverCompetitionStandardsRecoveryTests(TransactionTestCase):
    def test_cutover_renames_tables_and_migrates_legacy_training_cycle_targets(self):
        competition_type = CompetitionType.objects.create(code='WSC-CUTOVER', name='切换测试赛事')
        project = Project.objects.create(
            competition_type=competition_type,
            code='CUTOVER',
            name='切换测试赛项',
        )
        module_set = project.get_or_create_default_standard_module_set()
        StandardModule.objects.create(
            project=project,
            module_set=module_set,
            code='A',
            name='切换测试模块',
        )
        competition = Competition.objects.create(
            competition_type=competition_type,
            name='第48届世界技能大赛',
            code='WSC48-CUTOVER',
        )
        competition_project = CompetitionProject.objects.create(
            competition=competition,
            project=project,
        )
        training_cycle = TrainingCycle.objects.create(
            code='TC-CUTOVER',
            name='切换测试周期',
            project=project,
            module_set=module_set,
            start_date=date(2026, 1, 1),
        )

        old_content_type = ContentType.objects.create(app_label='curriculum', model='project')
        Permission.objects.create(
            name='旧项目查看权限',
            codename='view_project_legacy',
            content_type=old_content_type,
        )
        self._convert_to_legacy_shape(
            training_cycle_id=training_cycle.pk,
            competition_project_id=competition_project.pk,
        )

        output = StringIO()
        call_command('cutover_competition_standards', '--execute', stdout=output)

        self.assertIn('competition_standards 切换已完成', output.getvalue())
        self.assertTrue(self._table_exists('competition_standards_project'))
        self.assertFalse(self._table_exists('curriculum_project'))
        self.assertFalse(self._table_exists('trainingcycles_trainingcycle'))
        self.assertTrue(
            MigrationRecorder.Migration.objects.filter(app='competition_standards', name='0001_initial').exists()
        )
        self.assertFalse(MigrationRecorder.Migration.objects.filter(app__in=['curriculum', 'trainingcycles']).exists())
        self.assertTrue(
            MigrationRecorder.Migration.objects.filter(
                app='competitions',
                name='0004_competitiontrainingcycletarget',
            ).exists()
        )
        self.assertFalse(ContentType.objects.filter(app_label='curriculum', model='project').exists())
        self.assertTrue(
            Permission.objects.filter(
                codename='view_project_legacy',
                content_type__app_label='competition_standards',
            ).exists()
        )

        target = CompetitionTrainingCycleTarget.objects.get()
        self.assertEqual(target.training_cycle_id, training_cycle.pk)
        self.assertEqual(target.competition_project_id, competition_project.pk)
        self.assertEqual(target.kind, CompetitionTrainingCycleTarget.Kind.PRIMARY)
        self.assertNotIn(
            'primary_competition_project_id',
            self._get_table_columns('competition_standards_trainingcycle'),
        )

    def _convert_to_legacy_shape(self, *, training_cycle_id, competition_project_id):
        with connection.constraint_checks_disabled():
            with connection.schema_editor(atomic=False) as schema_editor:
                schema_editor.alter_db_table(
                    CompetitionType,
                    CompetitionType._meta.db_table,
                    'curriculum_competitiontype',
                )
                schema_editor.alter_db_table(
                    Project,
                    Project._meta.db_table,
                    'curriculum_project',
                )
                schema_editor.alter_db_table(
                    StandardModuleSet,
                    StandardModuleSet._meta.db_table,
                    'curriculum_standardmoduleset',
                )
                schema_editor.alter_db_table(
                    StandardModule,
                    StandardModule._meta.db_table,
                    'curriculum_standardmodule',
                )
                schema_editor.alter_db_table(
                    TrainingCycle,
                    TrainingCycle._meta.db_table,
                    'trainingcycles_trainingcycle',
                )

            with connection.cursor() as cursor:
                cursor.execute('DROP TABLE IF EXISTS competitions_competitiontrainingcycletarget')
                cursor.execute(
                    'ALTER TABLE trainingcycles_trainingcycle '
                    'ADD COLUMN primary_competition_project_id bigint NULL'
                )
                cursor.execute(
                    'ALTER TABLE trainingcycles_trainingcycle '
                    'ADD COLUMN reference_competition_project_id bigint NULL'
                )
                cursor.execute(
                    'UPDATE trainingcycles_trainingcycle '
                    'SET primary_competition_project_id = %s WHERE id = %s',
                    [competition_project_id, training_cycle_id],
                )

        MigrationRecorder.Migration.objects.filter(app='competition_standards').delete()
        MigrationRecorder.Migration.objects.filter(
            app='competitions',
            name='0004_competitiontrainingcycletarget',
        ).delete()
        MigrationRecorder.Migration.objects.get_or_create(app='curriculum', name='0001_initial')
        MigrationRecorder.Migration.objects.get_or_create(app='trainingcycles', name='0001_initial')

    def _table_exists(self, table_name):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = %s",
                [table_name],
            )
            return cursor.fetchone() is not None

    def _get_table_columns(self, table_name):
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table_name)
        return {column.name for column in description}
