from decimal import Decimal
from io import StringIO
from itertools import count

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase

from core.bootstrap_engine import bootstrap_defaults
from behaviors.models import (
    ConductCategory,
    ConductItem,
    ConductNature,
    ConductSeverity,
    ConductSeverityRule,
)


CONDUCT_NATURE_REWARD = ConductNature.REWARD
CONDUCT_NATURE_PENALTY = ConductNature.PENALTY
CONDUCT_SEVERITY_MINOR = 'MINOR'
CONDUCT_SEVERITY_MODERATE = 'MODERATE'
_TEST_CODE_SEQUENCE = count(1)


def severity(code):
    return ConductSeverity.objects.get(code=code)


def next_test_code(prefix):
    return f'test-{prefix}-{next(_TEST_CODE_SEQUENCE)}'


class ConductItemValidationTestCase(TestCase):
    """奖惩事项默认分值应严格匹配分类性质。"""

    def setUp(self):
        self.reward_category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='奖励分类',
        )
        self.penalty_category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_PENALTY,
            name='惩罚分类',
        )

    def test_reward_item_default_score_must_be_positive(self):
        item = ConductItem(
            code=next_test_code('item'),
            category=self.reward_category,
            name='奖励事项',
            default_score=Decimal('0.00'),
        )

        with self.assertRaises(ValidationError) as context:
            item.full_clean()

        self.assertIn('default_score', context.exception.message_dict)

    def test_penalty_item_default_score_must_be_negative(self):
        item = ConductItem(
            code=next_test_code('item'),
            category=self.penalty_category,
            name='惩罚事项',
            default_score=Decimal('0.00'),
        )

        with self.assertRaises(ValidationError) as context:
            item.full_clean()

        self.assertIn('default_score', context.exception.message_dict)


class ConductBootstrapTestCase(TestCase):
    """Bootstrap 应提供代表性的奖惩分类与事项。"""

    def setUp(self):
        bootstrap_defaults()

    def test_bootstrap_seeds_representative_categories_and_items(self):
        self.assertEqual(ConductCategory.objects.count(), 2)
        self.assertEqual(ConductItem.objects.count(), 7)

        attendance_category = ConductCategory.objects.get(
            nature=CONDUCT_NATURE_PENALTY,
            name='考勤',
        )
        competition_category = ConductCategory.objects.get(
            nature=CONDUCT_NATURE_REWARD,
            name='竞赛获奖',
        )

        self.assertEqual(
            dict(attendance_category.items.values_list('name', 'default_score')),
            {
                '迟到': Decimal('-1.00'),
                '早退': Decimal('-1.00'),
                '旷课': Decimal('-5.00'),
            },
        )
        self.assertEqual(
            dict(competition_category.items.values_list('name', 'default_score')),
            {
                '市级': Decimal('1.00'),
                '省级': Decimal('5.00'),
                '国家级': Decimal('10.00'),
                '世界级': Decimal('20.00'),
            },
        )

    def test_bootstrap_does_not_make_an_inactive_severity_the_default(self):
        moderate = severity(CONDUCT_SEVERITY_MODERATE)
        ConductSeverityRule.objects.filter(
            severity=moderate,
        ).delete()
        moderate.is_active = False
        moderate.save(update_fields=['is_active'])

        bootstrap_defaults()

        recreated = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_REWARD,
            severity=moderate,
        )
        self.assertFalse(recreated.is_default)
        moderate.refresh_from_db()
        self.assertFalse(moderate.is_active)


class ConductSeverityRuleValidationTestCase(TestCase):
    """严重程度规则应使用非负系数。"""

    def test_multiplier_cannot_be_negative(self):
        rule = ConductSeverityRule(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            label='表扬',
            multiplier=Decimal('-1.00'),
        )

        with self.assertRaises(ValidationError) as context:
            rule.full_clean()

        self.assertIn('multiplier', context.exception.message_dict)

    def test_default_severity_cannot_be_deactivated_before_rules_are_adjusted(self):
        moderate = severity(CONDUCT_SEVERITY_MODERATE)
        moderate.is_active = False

        with self.assertRaises(ValidationError) as context:
            moderate.full_clean()

        self.assertIn('is_active', context.exception.message_dict)

    def test_zero_multiplier_is_allowed(self):
        rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_PENALTY,
            severity=severity(CONDUCT_SEVERITY_MINOR),
        )

        rule.full_clean()

    def test_severity_labels_are_mapped_by_nature(self):
        reward_rule = ConductSeverityRule(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            label='表扬',
            multiplier=Decimal('1.00'),
        )
        penalty_rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_PENALTY,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
        )

        self.assertEqual(reward_rule.severity_label, '表扬')
        self.assertEqual(penalty_rule.severity_label, '一般')


class ConductCutoverCommandTests(TestCase):
    def test_cutover_command_is_noop_on_fresh_behaviors_schema(self):
        stdout = StringIO()

        call_command('cutover_conduct_to_behaviors', stdout=stdout)

        self.assertIn('当前数据库与文件目录已经使用 behaviors，无需切换。', stdout.getvalue())


class ConductCutoverRecoveryTests(TransactionTestCase):
    def test_cutover_command_recovers_dual_table_state_when_new_table_is_empty(self):
        category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='恢复奖励分类',
        )
        MigrationRecorder.Migration.objects.create(app='conduct', name='0001_initial')
        old_content_type = ContentType.objects.create(app_label='conduct', model='conductcategory')
        Permission.objects.create(
            name='旧奖惩查看权限',
            codename='view_conductcategory_legacy',
            content_type=old_content_type,
        )

        self.addCleanup(
            lambda: connection.cursor().execute('DROP TABLE IF EXISTS conduct_conductcategory')
        )
        self.addCleanup(
            lambda: connection.cursor().execute('DROP TABLE IF EXISTS behaviors_conductcategory_empty_backup')
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = %s",
                ['behaviors_conductcategory'],
            )
            create_sql = cursor.fetchone()[0].replace(
                '"behaviors_conductcategory"',
                '"conduct_conductcategory"',
                1,
            )
            cursor.execute(create_sql)
            cursor.execute('INSERT INTO conduct_conductcategory SELECT * FROM behaviors_conductcategory')
            cursor.execute('DELETE FROM behaviors_conductcategory')

        stdout = StringIO()
        call_command('cutover_conduct_to_behaviors', '--execute', stdout=stdout)

        self.assertIn('conduct 已切换为 behaviors', stdout.getvalue())
        self.assertEqual(ConductCategory.objects.count(), 1)
        self.assertEqual(ConductCategory.objects.get().pk, category.pk)
        self.assertFalse(MigrationRecorder.Migration.objects.filter(app='conduct').exists())
        self.assertFalse(ContentType.objects.filter(app_label='conduct', model='conductcategory').exists())
        self.assertTrue(
            Permission.objects.filter(
                codename='view_conductcategory_legacy',
                content_type__app_label='behaviors',
            ).exists()
        )

    def test_cutover_command_rejects_legacy_severity_rule_schema(self):
        self.addCleanup(
            lambda: connection.cursor().execute('DROP TABLE IF EXISTS conduct_conductseverityrule')
        )
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE conduct_conductseverityrule (
                    id INTEGER PRIMARY KEY,
                    nature VARCHAR(20) NOT NULL,
                    severity VARCHAR(20) NOT NULL,
                    multiplier DECIMAL NOT NULL,
                    "order" INTEGER NOT NULL
                )
                '''
            )

        with self.assertRaisesMessage(CommandError, '结构早于当前 behaviors 模型'):
            call_command('cutover_conduct_to_behaviors', '--execute')
