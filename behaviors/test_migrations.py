from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ConductCatalogMigrationTests(TransactionTestCase):
    migrate_from = ('behaviors', '0015_alter_conductrecord_attachment')
    migrate_to = ('behaviors', '0018_finalize_conduct_catalog_fields')

    @staticmethod
    def targets(executor, target):
        return [
            *[node for node in executor.loader.graph.leaf_nodes() if node[0] != 'behaviors'],
            target,
        ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        User = old_apps.get_model('auth', 'User')
        ConductCategory = old_apps.get_model('behaviors', 'ConductCategory')
        ConductItem = old_apps.get_model('behaviors', 'ConductItem')
        ConductRecord = old_apps.get_model('behaviors', 'ConductRecord')
        ConductSeverityRule = old_apps.get_model('behaviors', 'ConductSeverityRule')

        user = User.objects.create(username='conduct-catalog-migration')
        attendance = ConductCategory.objects.create(nature='PENALTY', name='考勤')
        renamed = ConductCategory.objects.create(nature='REWARD', name='已改名竞赛奖励')
        warning = ConductCategory.objects.create(nature='WARNING', name='历史警告')
        late = ConductItem.objects.create(
            category=attendance,
            name='迟到',
            default_score=Decimal('-1.00'),
        )
        custom_item = ConductItem.objects.create(
            category=renamed,
            name='市级',
            default_score=Decimal('1.00'),
        )
        warning_item = ConductItem.objects.create(
            category=warning,
            name='口头提醒',
            default_score=Decimal('0.00'),
        )
        ConductSeverityRule.objects.create(
            nature='PENALTY',
            severity='MODERATE',
            multiplier=Decimal('1.00'),
            order=20,
        )
        warning_rule = ConductSeverityRule.objects.create(
            nature='WARNING',
            severity='LEGACY_LEVEL',
            multiplier=Decimal('0.50'),
            order=10,
        )
        self.record_pk = ConductRecord.objects.create(
            student=user,
            item=warning_item,
            severity='LEGACY_LEVEL',
            reason='历史警告记录',
        ).pk
        self.attendance_pk = attendance.pk
        self.renamed_pk = renamed.pk
        self.late_pk = late.pk
        self.custom_item_pk = custom_item.pk
        self.warning_rule_pk = warning_rule.pk

        executor = MigrationExecutor(connection)
        to_targets = self.targets(executor, self.migrate_to)
        executor.migrate(to_targets)
        self.apps = executor.loader.project_state(to_targets).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_severity_relations_codes_and_historical_nature_survive(self):
        ConductCategory = self.apps.get_model('behaviors', 'ConductCategory')
        ConductItem = self.apps.get_model('behaviors', 'ConductItem')
        ConductRecord = self.apps.get_model('behaviors', 'ConductRecord')
        ConductSeverityRule = self.apps.get_model('behaviors', 'ConductSeverityRule')

        self.assertEqual(ConductCategory.objects.get(pk=self.attendance_pk).code, 'attendance')
        self.assertEqual(
            ConductCategory.objects.get(pk=self.renamed_pk).code,
            f'legacy-category-{self.renamed_pk}',
        )
        self.assertEqual(ConductItem.objects.get(pk=self.late_pk).code, 'late')
        self.assertEqual(
            ConductItem.objects.get(pk=self.custom_item_pk).code,
            f'legacy-item-{self.custom_item_pk}',
        )
        record = ConductRecord.objects.select_related('severity').get(pk=self.record_pk)
        self.assertEqual(record.severity.code, 'LEGACY_LEVEL')
        self.assertFalse(record.severity.is_active)
        warning_rule = ConductSeverityRule.objects.select_related('severity').get(pk=self.warning_rule_pk)
        self.assertEqual(warning_rule.nature, 'WARNING')
        self.assertEqual(warning_rule.severity.code, 'LEGACY_LEVEL')
        self.assertEqual(warning_rule.multiplier, Decimal('0.50'))
        self.assertFalse(warning_rule.is_default)

        executor = MigrationExecutor(connection)
        from_targets = self.targets(executor, self.migrate_from)
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        OldConductRecord = old_apps.get_model('behaviors', 'ConductRecord')
        OldConductSeverityRule = old_apps.get_model('behaviors', 'ConductSeverityRule')
        self.assertEqual(OldConductRecord.objects.get(pk=self.record_pk).severity, 'LEGACY_LEVEL')
        restored_rule = OldConductSeverityRule.objects.get(pk=self.warning_rule_pk)
        self.assertEqual(restored_rule.nature, 'WARNING')
        self.assertEqual(restored_rule.severity, 'LEGACY_LEVEL')
