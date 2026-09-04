import json
from decimal import Decimal
from io import StringIO
from itertools import count
from pathlib import Path

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from behaviors.admin import ConductCategoryAdmin, ConductItemAdmin, ConductRecordAdmin, ConductSeverityRuleAdmin, ConductSummaryAdmin
from core.bootstrap_engine import bootstrap_defaults
from behaviors.models import (
    ConductCategory,
    ConductItem,
    ConductNature,
    ConductRecord,
    ConductSeverity,
    ConductSeverityRule,
    ConductSummary,
)
from behaviors.services import prepare_conduct_record_for_save


User = get_user_model()
CONDUCT_NATURE_REWARD = ConductNature.REWARD
CONDUCT_NATURE_PENALTY = ConductNature.PENALTY
CONDUCT_SEVERITY_MINOR = 'MINOR'
CONDUCT_SEVERITY_MODERATE = 'MODERATE'
CONDUCT_SEVERITY_SEVERE = 'SEVERE'
CONDUCT_PENALTY_SEVERITY_NAMES = {
    'MINOR': '轻微',
    'MODERATE': '一般',
    'SEVERE': '严重',
}
_TEST_CODE_SEQUENCE = count(1)


def severity(code):
    return ConductSeverity.objects.get(code=code)


def next_test_code(prefix):
    return f'test-{prefix}-{next(_TEST_CODE_SEQUENCE)}'


def create_conduct_subject_group(name="奖惩对象组"):
    group = Group.objects.create(name=name)
    group.permissions.add(
        Permission.objects.get(
            content_type__app_label="behaviors",
            codename="be_conduct_subject",
        )
    )
    return group


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


class ConductRecordValidationTestCase(TestCase):
    """奖惩记录应遵守选手范围与审核状态流。"""

    def setUp(self):
        self.competitor_group = create_conduct_subject_group()
        self.student = User.objects.create_user(username='student', password='testpass123')
        self.student.groups.add(self.competitor_group)
        self.outsider = User.objects.create_user(username='outsider', password='testpass123')
        self.recorder = User.objects.create_user(username='recorder', password='testpass123')
        self.reviewer = User.objects.create_user(username='reviewer', password='testpass123')

        self.category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='学习表现',
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
        )
        self.item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=self.category,
            name='课堂表现优秀',
            default_score=Decimal('5.00'),
        )

    def test_record_requires_competitor_student(self):
        record = ConductRecord(
            student=self.outsider,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='非选手用户不应被录入',
            recorded_by=self.recorder,
        )

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn('student', context.exception.message_dict)

    def test_record_score_uses_item_default_score_and_multiplier(self):
        record = ConductRecord(
            student=self.student,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='一般情形按默认分值计算',
            recorded_by=self.recorder,
        )

        record.full_clean()

        self.assertEqual(record.score, Decimal('5.00'))
        self.assertEqual(record.severity_label, '表扬')

    def test_attachment_upload_path_uses_behaviors_directory(self):
        record = ConductRecord.objects.create(
            student=self.student,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='上传奖惩附件',
            recorded_by=self.recorder,
            attachment=SimpleUploadedFile('evidence.pdf', b'%PDF-1.4\nbehavior test', content_type='application/pdf'),
        )
        self.addCleanup(record.attachment.delete, False)

        self.assertFalse(record.attachment.name.startswith('behaviors/'))
        self.assertEqual(Path(record.attachment.path).parent.parent.name, 'behaviors')

    def test_record_requires_configured_severity_rule(self):
        ConductSeverityRule.objects.filter(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_SEVERE),
        ).delete()

        record = ConductRecord(
            student=self.student,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_SEVERE),
            reason='未配置严重程度规则',
            recorded_by=self.recorder,
        )

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn('severity', context.exception.message_dict)

    def test_rejected_record_requires_review_note(self):
        record = ConductRecord(
            student=self.student,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='需要驳回',
            recorded_by=self.recorder,
            status=ConductRecord.Status.REJECTED,
        )

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn('review_note', context.exception.message_dict)

    def test_pending_record_cannot_store_review_metadata(self):
        record = ConductRecord(
            student=self.student,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='待审核记录不能预先写审核信息',
            recorded_by=self.recorder,
            review_note='先写意见',
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn('review_note', context.exception.message_dict)
        self.assertIn('status', context.exception.message_dict)

    def test_reviewed_record_cannot_change_status_again(self):
        record = ConductRecord.objects.create(
            student=self.student,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='先通过再尝试改状态',
            recorded_by=self.recorder,
            status=ConductRecord.Status.APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

        record.status = ConductRecord.Status.REJECTED
        record.review_note = '再次驳回'

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn('status', context.exception.message_dict)


class ConductSummarySynchronizationTestCase(TestCase):
    """默认分值与严重程度系数变更后，汇总应自动重算。"""

    def setUp(self):
        competitor_group = create_conduct_subject_group()
        self.student = User.objects.create_user(username='summary-student', password='testpass123')
        self.student.groups.add(competitor_group)
        self.recorder = User.objects.create_user(username='summary-recorder', password='testpass123')
        self.reviewer = User.objects.create_user(username='summary-reviewer', password='testpass123')

        self.category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='竞赛荣誉',
        )
        self.rule, _ = ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
        )
        self.item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=self.category,
            name='获奖',
            default_score=Decimal('5.00'),
        )
        ConductRecord.objects.create(
            student=self.student,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='获奖一次',
            recorded_by=self.recorder,
            status=ConductRecord.Status.APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

    def test_item_default_score_change_recalculates_summary(self):
        summary = ConductSummary.objects.get(student=self.student)
        self.assertEqual(summary.total_score, Decimal('5.00'))

        self.item.default_score = Decimal('8.00')
        self.item.save()

        summary.refresh_from_db()
        self.assertEqual(summary.total_score, Decimal('8.00'))
        self.assertEqual(summary.reward_count, 1)
        self.assertEqual(summary.penalty_count, 0)

    def test_rule_multiplier_change_recalculates_summary(self):
        summary = ConductSummary.objects.get(student=self.student)
        self.assertEqual(summary.total_score, Decimal('5.00'))

        self.rule.multiplier = Decimal('2.00')
        self.rule.save()

        summary.refresh_from_db()
        self.assertEqual(summary.total_score, Decimal('10.00'))
        self.assertEqual(summary.reward_count, 1)
        self.assertEqual(summary.penalty_count, 0)


class ConductSummaryZeroScoreCountTestCase(TestCase):
    """零分惩罚仍应计入惩罚次数。"""

    def test_warning_style_penalty_counts_but_does_not_reduce_total(self):
        competitor_group = create_conduct_subject_group()
        student = User.objects.create_user(username='warning-student', password='testpass123')
        student.groups.add(competitor_group)
        recorder = User.objects.create_user(username='warning-recorder', password='testpass123')
        reviewer = User.objects.create_user(username='warning-reviewer', password='testpass123')

        category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_PENALTY,
            name='纪律问题',
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_PENALTY,
            severity=severity(CONDUCT_SEVERITY_MINOR),
            defaults={'multiplier': Decimal('0.00'), 'order': 10},
        )
        item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=category,
            name='迟到',
            default_score=Decimal('-2.00'),
        )

        ConductRecord.objects.create(
            student=student,
            item=item,
            severity=severity(CONDUCT_SEVERITY_MINOR),
            reason='只做警告，不扣分',
            recorded_by=recorder,
            status=ConductRecord.Status.APPROVED,
            reviewed_by=reviewer,
            reviewed_at=timezone.now(),
        )

        summary = ConductSummary.objects.get(student=student)
        self.assertEqual(summary.total_score, Decimal('0.00'))
        self.assertEqual(summary.penalty_count, 1)
        self.assertEqual(summary.reward_count, 0)


class ConductSummaryAdminTestCase(TestCase):
    def test_summary_cannot_be_deleted_directly_in_admin(self):
        request = RequestFactory().get('/admin/behaviors/conductsummary/')
        request.user = User.objects.create_superuser('summary-admin', password='testpass123')
        model_admin = ConductSummaryAdmin(ConductSummary, AdminSite())

        self.assertFalse(model_admin.has_delete_permission(request))


class ConductSeverityRuleAdminDeleteTestCase(TestCase):
    def setUp(self):
        self.request = RequestFactory().get('/admin/behaviors/conductseverityrule/')
        self.request.user = User.objects.create_superuser('severity-rule-admin', password='testpass123')
        self.model_admin = ConductSeverityRuleAdmin(ConductSeverityRule, AdminSite())

    def test_unused_rule_can_be_deleted(self):
        rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MINOR),
        )

        self.assertTrue(self.model_admin.has_delete_permission(self.request, rule))
        self.client.force_login(self.request.user)
        response = self.client.post(
            reverse('admin:behaviors_conductseverityrule_delete', args=[rule.pk]),
            {'post': 'yes'},
        )

        self.assertRedirects(response, reverse('admin:behaviors_conductseverityrule_changelist'))
        self.assertFalse(ConductSeverityRule.objects.filter(pk=rule.pk).exists())

    def test_rule_used_by_conduct_record_cannot_be_deleted(self):
        competitor_group = create_conduct_subject_group()
        student = User.objects.create_user(username='rule-delete-student', password='testpass123')
        student.groups.add(competitor_group)
        recorder = User.objects.create_user(username='rule-delete-recorder', password='testpass123')
        category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='系数删除测试分类',
        )
        item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=category,
            name='系数删除测试事项',
            default_score=Decimal('1.00'),
        )
        rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MINOR),
        )
        ConductRecord.objects.create(
            student=student,
            item=item,
            severity=rule.severity,
            reason='保留历史计分规则',
            recorded_by=recorder,
        )

        self.assertFalse(self.model_admin.has_delete_permission(self.request, rule))

    def test_bulk_delete_reports_used_rule_as_missing_permission(self):
        competitor_group = create_conduct_subject_group()
        student = User.objects.create_user(username='rule-bulk-delete-student', password='testpass123')
        student.groups.add(competitor_group)
        recorder = User.objects.create_user(username='rule-bulk-delete-recorder', password='testpass123')
        category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='系数批量删除测试分类',
        )
        item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=category,
            name='系数批量删除测试事项',
            default_score=Decimal('1.00'),
        )
        used_rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MINOR),
        )
        unused_rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_SEVERE),
        )
        ConductRecord.objects.create(
            student=student,
            item=item,
            severity=used_rule.severity,
            reason='批量删除也必须保留历史计分规则',
            recorded_by=recorder,
        )

        _, _, perms_needed, _ = self.model_admin.get_deleted_objects(
            ConductSeverityRule.objects.filter(pk__in=[used_rule.pk, unused_rule.pk]),
            self.request,
        )

        self.assertIn('已被奖惩记录使用的严重程度系数规则', perms_needed)


class ConductRecordAdminTestCase(TestCase):
    """仅保留后台时，admin 仍需区分录入与审核权限。"""

    def setUp(self):
        competitor_group = create_conduct_subject_group()
        self.student = User.objects.create_user(username='admin-student', password='testpass123')
        self.student.groups.add(competitor_group)

        self.recorder = User.objects.create_user(username='admin-recorder', password='testpass123')
        self.other_recorder = User.objects.create_user(username='admin-recorder-2', password='testpass123')
        self.reviewer = User.objects.create_user(username='admin-reviewer', password='testpass123')

        self.recorder.user_permissions.add(Permission.objects.get(codename='add_conduct_record'))
        self.other_recorder.user_permissions.add(Permission.objects.get(codename='add_conduct_record'))
        self.reviewer.user_permissions.add(Permission.objects.get(codename='review_conduct_record'))

        category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='后台测试分类',
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
        )
        item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=category,
            name='后台测试事项',
            default_score=Decimal('6.00'),
        )
        self.record = ConductRecord.objects.create(
            student=self.student,
            item=item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='待审核记录',
            recorded_by=self.recorder,
        )
        self.other_record = ConductRecord.objects.create(
            student=self.student,
            item=item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='其他人录入的记录',
            recorded_by=self.other_recorder,
        )

        self.factory = RequestFactory()
        self.admin = ConductRecordAdmin(ConductRecord, AdminSite())
        self.category_admin = ConductCategoryAdmin(ConductCategory, AdminSite())
        self.item_admin = ConductItemAdmin(ConductItem, AdminSite())
        self.rule_admin = ConductSeverityRuleAdmin(ConductSeverityRule, AdminSite())
        self.penalty_category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_PENALTY,
            name='后台惩罚分类',
        )
        self.penalty_item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=self.penalty_category,
            name='后台惩罚事项',
            default_score=Decimal('-2.00'),
        )

    def build_request(self, user):
        request = self.factory.get('/admin/behaviors/conductrecord/')
        request.user = user
        return request

    def test_recorder_queryset_only_contains_own_records(self):
        queryset = self.admin.get_queryset(self.build_request(self.recorder))

        self.assertQuerySetEqual(
            queryset.order_by('pk').values_list('pk', flat=True),
            [self.record.pk],
            transform=lambda value: value,
        )

    def test_reviewer_queryset_contains_all_records(self):
        queryset = self.admin.get_queryset(self.build_request(self.reviewer))

        self.assertQuerySetEqual(
            queryset.order_by('pk').values_list('pk', flat=True),
            [self.record.pk, self.other_record.pk],
            transform=lambda value: value,
        )

    def test_record_fieldsets_include_severity(self):
        fieldsets = self.admin.get_fieldsets(self.build_request(self.recorder))

        self.assertIn('severity', fieldsets[0][1]['fields'])

    def test_record_metadata_fields_include_update_audit(self):
        self.assertIn('updated_by', self.admin.metadata_fields)
        self.assertIn('updated_at', self.admin.metadata_fields)
        self.assertIn('updated_by_display', self.admin.list_display)
        self.assertIn('updated_at', self.admin.list_display)

    def test_item_admin_exposes_default_score_field(self):
        basic_fields = self.item_admin.fieldsets[0][1]['fields']

        self.assertIn('default_score', basic_fields)

    def test_existing_record_fieldset_includes_score_formula(self):
        fieldsets = self.admin.get_fieldsets(self.build_request(self.recorder), self.record)

        self.assertIn('score_formula_display', fieldsets[0][1]['fields'])

    def test_record_admin_form_uses_reward_specific_severity_labels(self):
        form_class = self.admin.get_form(self.build_request(self.recorder), self.record)
        form = form_class(instance=self.record)
        choices = dict(form.fields['severity'].choices)

        self.assertEqual(choices[CONDUCT_SEVERITY_MODERATE], '表扬（×1.00）')

    def test_inactive_severity_is_hidden_for_new_selection_but_kept_on_history(self):
        current_severity = severity(CONDUCT_SEVERITY_MODERATE)
        current_severity.is_active = False
        current_severity.save(update_fields=['is_active'])

        form_class = self.admin.get_form(self.build_request(self.recorder), self.record)
        history_form = form_class(instance=self.record)
        new_form = form_class(data={'item': self.record.item_id})

        self.assertIn(current_severity, history_form.fields['severity'].queryset)
        self.assertNotIn(current_severity, new_form.fields['severity'].queryset)

    def test_add_record_form_shows_placeholder_before_item_selection(self):
        form_class = self.admin.get_form(self.build_request(self.recorder))
        form = form_class()

        self.assertEqual(list(form.fields['severity'].choices), [('', '请先选择奖惩事项')])

    def test_record_admin_form_includes_dynamic_severity_refresh_url(self):
        form_class = self.admin.get_form(self.build_request(self.recorder))
        form = form_class()

        self.assertIn('data-severity-choices-url', str(form['item']))
        self.assertNotIn('data-default-severity', str(form['severity']))
        self.assertIn('data-placeholder-label', str(form['severity']))

    def test_severity_choices_endpoint_returns_reward_labels(self):
        request = self.factory.get(
            '/admin/behaviors/conductrecord/severity-choices/',
            {'item_id': self.record.item_id},
        )
        request.user = self.recorder

        response = self.admin.severity_choices_view(request)
        payload = json.loads(response.content)
        choices = {choice['value']: choice['label'] for choice in payload['choices']}

        self.assertEqual(choices[CONDUCT_SEVERITY_MODERATE], '表扬（×1.00）')

    def test_severity_choices_endpoint_does_not_guess_when_no_default_rule_exists(self):
        ConductSeverityRule.objects.filter(nature=CONDUCT_NATURE_REWARD).update(is_default=False)
        request = self.factory.get(
            '/admin/behaviors/conductrecord/severity-choices/',
            {'item_id': self.record.item_id},
        )
        request.user = self.recorder

        payload = json.loads(self.admin.severity_choices_view(request).content)

        self.assertEqual(payload['default'], '')
        self.assertEqual(payload['choices'][0], {
            'value': '',
            'label': '请选择程度（未配置默认项）',
        })

    def test_severity_choices_endpoint_returns_penalty_labels(self):
        request = self.factory.get(
            '/admin/behaviors/conductrecord/severity-choices/',
            {'item_id': self.penalty_item.pk},
        )
        request.user = self.recorder

        response = self.admin.severity_choices_view(request)
        payload = json.loads(response.content)
        choices = {choice['value']: choice['label'] for choice in payload['choices']}

        self.assertEqual(
            choices[CONDUCT_SEVERITY_MINOR],
            f'{CONDUCT_PENALTY_SEVERITY_NAMES[CONDUCT_SEVERITY_MINOR]}（×0.00）',
        )
        self.assertEqual(
            choices[CONDUCT_SEVERITY_MODERATE],
            f'{CONDUCT_PENALTY_SEVERITY_NAMES[CONDUCT_SEVERITY_MODERATE]}（×1.00）',
        )

    def test_rule_admin_form_uses_penalty_specific_severity_labels(self):
        penalty_rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_PENALTY,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
        )
        form_class = self.rule_admin.get_form(self.build_request(self.reviewer), penalty_rule)
        form = form_class(instance=penalty_rule)
        choices = dict(form.fields['severity'].choices)

        self.assertEqual(choices[CONDUCT_SEVERITY_MODERATE], '一般')

    def test_historical_warning_nature_is_displayed_raw_and_locked_in_admin(self):
        historical = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature='WARNING',
            name='历史警告分类',
        )

        readonly = self.category_admin.get_readonly_fields(
            self.build_request(self.reviewer),
            historical,
        )

        self.assertEqual(historical.nature_label, 'WARNING（历史）')
        self.assertIn('code', readonly)
        self.assertIn('nature', readonly)

    def test_recorder_cannot_edit_review_fields(self):
        readonly_fields = self.admin.get_readonly_fields(
            self.build_request(self.recorder),
            self.record,
        )

        self.assertIn('status', readonly_fields)
        self.assertIn('review_note', readonly_fields)
        self.assertTrue(self.admin.has_change_permission(self.build_request(self.recorder), self.record))

    def test_reviewer_can_approve_pending_record_and_admin_writes_review_metadata(self):
        request = self.build_request(self.reviewer)
        readonly_fields = self.admin.get_readonly_fields(request, self.record)

        self.assertIn('student', readonly_fields)
        self.assertNotIn('status', readonly_fields)

        record = ConductRecord.objects.get(pk=self.record.pk)
        record.status = ConductRecord.Status.APPROVED
        self.admin.save_model(request, record, form=None, change=True)

        record.refresh_from_db()
        summary = ConductSummary.objects.get(student=self.student)

        self.assertEqual(record.reviewed_by, self.reviewer)
        self.assertIsNotNone(record.reviewed_at)
        self.assertEqual(record.updated_by, self.reviewer)
        self.assertIsNotNone(record.updated_at)
        self.assertEqual(summary.total_score, Decimal('6.00'))
        self.assertEqual(record.score_formula, '+6.00 x 1.00 = +6.00')

    def test_reviewed_record_is_read_only_in_admin(self):
        self.record.status = ConductRecord.Status.APPROVED
        self.record.reviewed_by = self.reviewer
        self.record.reviewed_at = timezone.now()
        self.record.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        self.assertFalse(
            self.admin.has_change_permission(
                self.build_request(self.reviewer),
                self.record,
            )
        )


class ConductWorkflowServiceTests(TestCase):
    def setUp(self):
        competitor_group = create_conduct_subject_group()
        self.student = User.objects.create_user(username='workflow-student', password='testpass123')
        self.student.groups.add(competitor_group)
        self.recorder = User.objects.create_user(username='workflow-recorder', password='testpass123')
        self.reviewer = User.objects.create_user(username='workflow-reviewer', password='testpass123')
        category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='服务测试分类',
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
        )
        self.item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=category,
            name='服务测试事项',
            default_score=Decimal('3.00'),
        )

    def test_prepare_conduct_record_for_create_sets_recorder_and_pending_status(self):
        record = ConductRecord(
            student=self.student,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='创建时由 service 补齐记录信息',
            status=ConductRecord.Status.APPROVED,
        )

        prepare_conduct_record_for_save(record, actor=self.recorder, change=False)

        self.assertEqual(record.recorded_by, self.recorder)
        self.assertEqual(record.status, ConductRecord.Status.PENDING)

    def test_prepare_conduct_record_for_update_sets_review_metadata_on_first_review(self):
        record = ConductRecord.objects.create(
            student=self.student,
            item=self.item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='等待审核',
            recorded_by=self.recorder,
        )
        review_time = timezone.now()
        record.status = ConductRecord.Status.APPROVED

        prepare_conduct_record_for_save(record, actor=self.reviewer, change=True, now=review_time)

        self.assertEqual(record.updated_by, self.reviewer)
        self.assertEqual(record.reviewed_by, self.reviewer)
        self.assertEqual(record.reviewed_at, review_time)


class ConductUrlTests(TestCase):
    def test_conduct_record_list_is_mounted_at_app_root(self):
        self.assertEqual(reverse('behaviors:conductrecord_list'), '/behaviors/')


class ConductRecordListViewTests(TestCase):
    """奖惩记录列表应展示核心字段并隐藏录入元数据。"""

    def setUp(self):
        competitor_group = create_conduct_subject_group()
        self.student = User.objects.create_user(username='list-student', password='testpass123')
        self.student.groups.add(competitor_group)
        self.other_student = User.objects.create_user(username='list-other-student', password='testpass123')
        self.other_student.groups.add(competitor_group)
        self.recorder = User.objects.create_user(username='list-recorder', password='testpass123')
        self.viewer = User.objects.create_user(username='list-viewer', password='testpass123')
        view_permission = Permission.objects.get(
            content_type__app_label='behaviors', codename='view_conductrecord'
        )
        self.student.user_permissions.add(view_permission)
        self.viewer.user_permissions.add(
            view_permission,
            Permission.objects.get(
                content_type__app_label='behaviors', codename='view_all_conduct_records'
            ),
        )

        category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='列表测试分类',
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MINOR),
            defaults={'multiplier': Decimal('0.00'), 'order': 10},
        )
        item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=category,
            name='列表测试事项',
            default_score=Decimal('5.00'),
        )

        ConductRecord.objects.create(
            student=self.student,
            item=item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='课堂表现积极，主动帮助同学',
            recorded_by=self.recorder,
        )
        ConductRecord.objects.create(
            student=self.student,
            item=item,
            severity=severity(CONDUCT_SEVERITY_MINOR),
            reason='只做提醒，不计分',
            recorded_by=self.recorder,
        )
        ConductRecord.objects.create(
            student=self.other_student,
            item=item,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            reason='不应显示的其他学生原因',
            recorded_by=self.recorder,
        )

    def test_student_list_shows_nature_and_reason_without_recorded_metadata(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('behaviors:conductrecord_list'))
        content = response.content.decode()

        self.assertContains(response, '奖惩性质')
        self.assertContains(response, '具体原因/描述')
        self.assertNotContains(response, '记录人')
        self.assertNotContains(response, '记录时间')
        self.assertLess(content.index('奖惩性质'), content.index('奖惩事项'))
        self.assertContains(response, '奖励')
        self.assertContains(response, '课堂表现积极，主动帮助同学')
        self.assertNotContains(response, '不应显示的其他学生原因')

    def test_zero_score_is_rendered_without_sign(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('behaviors:conductrecord_list'))

        self.assertContains(response, '0.0')
        self.assertNotContains(response, '+0.0')
        self.assertNotContains(response, '-0.0')

    def test_view_all_permission_user_can_see_other_students_records(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse('behaviors:conductrecord_list'))

        self.assertContains(response, '课堂表现积极，主动帮助同学')
        self.assertContains(response, '不应显示的其他学生原因')


class ConductRecordCreateViewTests(TestCase):
    def setUp(self):
        competitor_group = create_conduct_subject_group()
        self.student = User.objects.create_user(username='create-student', password='testpass123')
        self.student.groups.add(competitor_group)
        self.recorder = User.objects.create_user(username='create-recorder', password='testpass123')
        self.recorder.user_permissions.add(Permission.objects.get(codename='add_conduct_record'))
        self.recorder.user_permissions.add(
            Permission.objects.get(
                content_type__app_label='behaviors', codename='view_conductrecord'
            )
        )

        self.category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='录入测试分类',
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
        )
        self.item = ConductItem.objects.create(
            code=next_test_code('item'),
            category=self.category,
            name='录入测试事项',
            default_score=Decimal('4.00'),
        )

    def test_create_view_sets_recorded_by_and_pending_status(self):
        self.client.force_login(self.recorder)

        response = self.client.post(
            reverse('behaviors:conductrecord_create'),
            data={
                'student': self.student.pk,
                'nature': CONDUCT_NATURE_REWARD,
                'item': self.item.pk,
                'severity': CONDUCT_SEVERITY_MODERATE,
                'occurred_date': timezone.localdate().isoformat(),
                'reason': '前台录入测试',
            },
        )

        self.assertRedirects(response, reverse('behaviors:conductrecord_list'))

        record = ConductRecord.objects.get(reason='前台录入测试')
        self.assertEqual(record.recorded_by, self.recorder)
        self.assertEqual(record.status, ConductRecord.Status.PENDING)


class ConductAuditAdminTestCase(TestCase):
    """录入模型应记录创建人与更新人。"""

    def setUp(self):
        self.creator = User.objects.create_user(username='audit-creator', password='testpass123')
        self.updater = User.objects.create_user(username='audit-updater', password='testpass123')
        self.category_admin = ConductCategoryAdmin(ConductCategory, AdminSite())
        self.item_admin = ConductItemAdmin(ConductItem, AdminSite())
        self.rule_admin = ConductSeverityRuleAdmin(ConductSeverityRule, AdminSite())
        self.factory = RequestFactory()

        self.reward_category = ConductCategory.objects.create(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_REWARD,
            name='审计奖励分类',
        )

    def build_request(self, user):
        request = self.factory.get('/admin/behaviors/')
        request.user = user
        return request

    def test_category_admin_tracks_creator_and_updater(self):
        category = ConductCategory(
            code=next_test_code('category'),
            nature=CONDUCT_NATURE_PENALTY,
            name='审计惩罚分类',
        )

        self.category_admin.save_model(self.build_request(self.creator), category, form=None, change=False)
        category.refresh_from_db()
        self.assertEqual(category.created_by, self.creator)
        self.assertIsNone(category.updated_by)

        category.description = '已更新'
        self.category_admin.save_model(self.build_request(self.updater), category, form=None, change=True)
        category.refresh_from_db()
        self.assertEqual(category.updated_by, self.updater)

    def test_audited_models_use_creator_verbose_name(self):
        self.assertEqual(ConductCategory._meta.get_field('created_by').verbose_name, '创建人')
        self.assertEqual(ConductItem._meta.get_field('created_by').verbose_name, '创建人')
        self.assertEqual(ConductSeverityRule._meta.get_field('created_by').verbose_name, '创建人')

    def test_admin_list_display_includes_audit_columns(self):
        self.assertIn('created_by_display', self.category_admin.list_display)
        self.assertIn('updated_by_display', self.category_admin.list_display)
        self.assertIn('created_by_display', self.item_admin.list_display)
        self.assertIn('updated_by_display', self.item_admin.list_display)
        self.assertIn('created_by_display', self.rule_admin.list_display)
        self.assertIn('updated_by_display', self.rule_admin.list_display)

    def test_item_admin_tracks_creator_and_updater(self):
        item = ConductItem(
            code=next_test_code('item'),
            category=self.reward_category,
            name='审计事项',
            default_score=Decimal('3.00'),
        )

        self.item_admin.save_model(self.build_request(self.creator), item, form=None, change=False)
        item.refresh_from_db()
        self.assertEqual(item.created_by, self.creator)
        self.assertIsNone(item.updated_by)

        item.description = '已更新'
        self.item_admin.save_model(self.build_request(self.updater), item, form=None, change=True)
        item.refresh_from_db()
        self.assertEqual(item.updated_by, self.updater)

    def test_rule_admin_tracks_creator_and_updater(self):
        ConductSeverityRule.objects.filter(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
        ).delete()

        rule = ConductSeverityRule(
            nature=CONDUCT_NATURE_REWARD,
            severity=severity(CONDUCT_SEVERITY_MODERATE),
            label='表扬',
            multiplier=Decimal('1.00'),
        )

        self.rule_admin.save_model(self.build_request(self.creator), rule, form=None, change=False)
        rule.refresh_from_db()
        self.assertEqual(rule.created_by, self.creator)
        self.assertIsNone(rule.updated_by)

        rule.multiplier = Decimal('2.00')
        self.rule_admin.save_model(self.build_request(self.updater), rule, form=None, change=True)
        rule.refresh_from_db()
        self.assertEqual(rule.updated_by, self.updater)


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
