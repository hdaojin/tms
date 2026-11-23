from decimal import Decimal
from uuid import uuid4

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


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
        ConductSeverityRule.objects.update_or_create(
            nature='PENALTY', severity='MODERATE',
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
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
        self.late_record_pk = ConductRecord.objects.create(
            student=user,
            item=late,
            severity='MODERATE',
            reason='历史迟到记录',
            status='APPROVED',
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


    def test_cycle_migration_freezes_existing_score_and_nature(self):
        record_model = self.apps.get_model('behaviors', 'ConductRecord')
        record = record_model.objects.get(pk=self.late_record_pk)
        self.apps.get_model('behaviors', 'ConductSeverityRule').objects.filter(
            nature='PENALTY', severity_id=record.severity_id,
        ).update(multiplier=Decimal('1.50'))
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        executor.migrate(targets)
        latest = executor.loader.project_state(targets).apps
        record = latest.get_model('behaviors', 'ConductRecord').objects.get(pk=self.late_record_pk)
        self.assertEqual(record.frozen_points, Decimal('-1.5000'))
        self.assertEqual(record.frozen_nature, 'PENALTY')


class UnifiedLedgerMigrationTests(TransactionTestCase):
    def test_merge_preserves_ids_amounts_audit_attachments_and_catalog_identity(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        prior = ('behaviors', '0021_remove_conductcategory_uniq_conduct_category_nature_name_and_more')
        previous = ConductCatalogMigrationTests.targets(executor, prior)
        executor.migrate(previous)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        apps = executor.loader.project_state(previous).apps
        user = apps.get_model('auth', 'User').objects.create(username='unified-ledger-migration')
        project = apps.get_model('standards', 'SkillProject').objects.create(code='ledger', name='账本迁移')
        now = timezone.now()
        cycle = apps.get_model('training', 'TrainingCycle').objects.create(
            code='ledger', name='奖惩周期', start_date=now.date(), skill_project=project,
        )

        def model(name):
            return apps.get_model('behaviors', name)

        category = model('ConductCategory').objects.create(nature='REWARD', name='竞赛获奖示例', code='shared')
        duplicate = model('ConductCategory').objects.create(
            nature='REWARD', name=category.name, code='scoped', cycle=cycle,
        )
        shared = model('ConductItem').objects.create(
            category=category, name='世界级', code='world', default_score=Decimal('20'),
        )
        item = model('ConductItem').objects.create(
            category=duplicate, name=shared.name, code='world-scoped', default_score=Decimal('30'),
        )
        conflict = model('ConductItem').objects.create(
            category=duplicate, name='省级', code='world', default_score=Decimal('7'),
        )
        severity = model('ConductSeverity').objects.create(code='MERGE_TEST', name='合并测试')
        old = model('ConductRecord').objects.create(
            pk=222, student=user, item=item, severity=severity, status='PENDING',
            occurred_date=now.date(), reason='旧记录', frozen_points=Decimal('1.2345'),
            frozen_nature='REWARD', attachment='old/evidence.pdf', recorded_by=user,
        )
        policy = model('ConductPolicy').objects.create(
            cycle=cycle, effective_date=now.date(), published_at=now, title='条例', issuer='教练组',
        )
        rules = [
            model('ConductPolicyRule').objects.create(
                item=item, policy=policy, section='competition', condition=label,
                points=points, item_label='发布时名称', category_label='发布时分类',
            )
            for points, label in [(30, '一等奖'), (25, '二等奖'), (20, '三等奖'), (15, '优胜奖')]
        ]
        cycle_record = model('CycleConductRecord').objects.create(
            pk=222, student=user, cycle=cycle, rule=rules[1], occurred_date=now.date(), submission_key=uuid4(),
            points=Decimal('25'), reason='已作废记录', attachment='cycle/evidence.pdf',
            status='void', created_by=user, reviewed_by=user, reviewed_at=now,
            voided_by=user, voided_at=now, void_note='测试作废',
        )

        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        apps = executor.loader.project_state(latest).apps
        records = model('ConductRecord').objects
        migrated = records.get(source_cycle_record_id=cycle_record.pk)
        persisted = records.get(pk=old.pk)
        self.assertNotEqual(migrated.pk, persisted.pk)
        self.assertIsNone(persisted.cycle_id)
        self.assertEqual(persisted.status, 'PENDING')
        self.assertEqual(persisted.frozen_points, Decimal('1.2345'))
        self.assertEqual(persisted.attachment.name, 'old/evidence.pdf')
        self.assertEqual(migrated.attachment.name, 'cycle/evidence.pdf')
        self.assertEqual(migrated.recorded_at, cycle_record.created_at)
        self.assertEqual(migrated.updated_at, cycle_record.updated_at)
        self.assertEqual(migrated.reviewed_by_id, user.pk)
        self.assertEqual(migrated.voided_by_id, user.pk)
        self.assertEqual(migrated.void_note, '测试作废')
        self.assertEqual(migrated.status, 'VOID')
        self.assertEqual(migrated.frozen_points, Decimal('25'))
        self.assertEqual(migrated.item_label, '发布时名称')
        self.assertEqual(migrated.item_id, shared.pk)
        self.assertEqual(persisted.item_id, shared.pk)
        self.assertEqual(model('ConductCategory').objects.filter(name=category.name).count(), 1)
        relocated = model('ConductItem').objects.get(pk=conflict.pk)
        self.assertEqual(relocated.category_id, category.pk)
        self.assertNotEqual(relocated.code, shared.code)
        rates = model('ConductPolicyRule').objects.filter(pk__in=[row.pk for row in rules]).order_by('pk')
        self.assertEqual(
            [(row.policy_item.base_score, row.multiplier) for row in rates],
            [(Decimal('20'), Decimal(value)) for value in ('1.50', '1.25', '1.00', '0.75')],
        )
