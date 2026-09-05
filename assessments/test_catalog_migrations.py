from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class AssessmentTypeMigrationTests(TransactionTestCase):
    migrate_from = ('assessments', '0004_assessment_scope_permissions')
    migrate_to = ('assessments', '0007_finalize_assessment_type')

    @staticmethod
    def targets(executor, target):
        return [
            *[node for node in executor.loader.graph.leaf_nodes() if node[0] not in {'assessments', 'scoring'}],
            ('scoring', '0002_unify_scoring_results_with_assessment_participants'),
            target,
        ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps

        User = old_apps.get_model('auth', 'User')
        SkillProject = old_apps.get_model('standards', 'SkillProject')
        Assessment = old_apps.get_model('assessments', 'Assessment')
        user = User.objects.create(username='assessment-type-migration')
        project = SkillProject.objects.create(code='TYPE-MIGRATION', name='类型迁移项目')
        self.known_pk = Assessment.objects.create(
            skill_project=project,
            assessment_type='mock',
            name='已知类型',
            code='TYPE-KNOWN',
            start_date=date(2026, 1, 1),
            created_by=user,
        ).pk
        self.unknown_pk = Assessment.objects.create(
            skill_project=project,
            assessment_type='legacy-kind',
            name='历史类型',
            code='TYPE-LEGACY',
            start_date=date(2026, 1, 2),
            created_by=user,
        ).pk

        executor = MigrationExecutor(connection)
        to_targets = self.targets(executor, self.migrate_to)
        executor.migrate(to_targets)
        self.apps = executor.loader.project_state(to_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_known_and_unknown_codes_survive_forward_and_reverse(self):
        Assessment = self.apps.get_model('assessments', 'Assessment')
        AssessmentType = self.apps.get_model('assessments', 'AssessmentType')

        self.assertEqual(Assessment.objects.get(pk=self.known_pk).assessment_type.code, 'mock')
        unknown = Assessment.objects.get(pk=self.unknown_pk).assessment_type
        self.assertEqual(unknown.code, 'legacy-kind')
        self.assertFalse(unknown.is_active)
        self.assertTrue(AssessmentType.objects.filter(code='competition').exists())

        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        OldAssessment = old_apps.get_model('assessments', 'Assessment')
        self.assertEqual(OldAssessment.objects.get(pk=self.known_pk).assessment_type, 'mock')
        self.assertEqual(OldAssessment.objects.get(pk=self.unknown_pk).assessment_type, 'legacy-kind')
