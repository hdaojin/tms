from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class FeedbackCategoryMigrationTests(TransactionTestCase):
    migrate_from = ('feedback', '0002_alter_feedback_category')
    migrate_to = ('feedback', '0005_finalize_feedback_category')

    @staticmethod
    def targets(executor, target):
        return [
            *[node for node in executor.loader.graph.leaf_nodes() if node[0] != 'feedback'],
            target,
        ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        User = old_apps.get_model('auth', 'User')
        Feedback = old_apps.get_model('feedback', 'Feedback')
        user = User.objects.create(username='feedback-category-migration')
        self.known_pk = Feedback.objects.create(
            category='bug',
            title='已知分类',
            content='正文',
            author=user,
        ).pk
        self.unknown_pk = Feedback.objects.create(
            category='legacy-feedback',
            title='历史分类',
            content='正文',
            author=user,
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
        Feedback = self.apps.get_model('feedback', 'Feedback')
        self.assertEqual(Feedback.objects.get(pk=self.known_pk).category.code, 'bug')
        unknown = Feedback.objects.get(pk=self.unknown_pk).category
        self.assertEqual(unknown.code, 'legacy-feedback')
        self.assertFalse(unknown.is_active)

        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        OldFeedback = old_apps.get_model('feedback', 'Feedback')
        self.assertEqual(OldFeedback.objects.get(pk=self.known_pk).category, 'bug')
        self.assertEqual(OldFeedback.objects.get(pk=self.unknown_pk).category, 'legacy-feedback')
