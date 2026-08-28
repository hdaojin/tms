from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class CountdownEventTypeMigrationTests(TransactionTestCase):
    migrate_from = ('event_countdown', '0003_alter_countdownevent_theme')
    migrate_to = ('event_countdown', '0006_finalize_countdown_event_type')

    @staticmethod
    def targets(executor, target):
        return [
            *[node for node in executor.loader.graph.leaf_nodes() if node[0] != 'event_countdown'],
            target,
        ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        CountdownEvent = old_apps.get_model('event_countdown', 'CountdownEvent')
        self.known_pk = CountdownEvent.objects.create(
            name='已知倒计时',
            event_type='training',
            target_at=timezone.now(),
        ).pk
        self.unknown_pk = CountdownEvent.objects.create(
            name='历史倒计时',
            event_type='legacy-event',
            target_at=timezone.now(),
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
        CountdownEvent = self.apps.get_model('event_countdown', 'CountdownEvent')
        self.assertEqual(CountdownEvent.objects.get(pk=self.known_pk).event_type.code, 'training')
        unknown = CountdownEvent.objects.get(pk=self.unknown_pk).event_type
        self.assertEqual(unknown.code, 'legacy-event')
        self.assertFalse(unknown.is_active)

        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        OldCountdownEvent = old_apps.get_model('event_countdown', 'CountdownEvent')
        self.assertEqual(OldCountdownEvent.objects.get(pk=self.known_pk).event_type, 'training')
        self.assertEqual(OldCountdownEvent.objects.get(pk=self.unknown_pk).event_type, 'legacy-event')
