import json
from io import StringIO
from decimal import Decimal
from pathlib import Path

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.constants import (
    CONDUCT_NATURE_PENALTY,
    CONDUCT_NATURE_REWARD,
    CONDUCT_PENALTY_SEVERITY_NAMES,
    CONDUCT_SEVERITY_MINOR,
    CONDUCT_SEVERITY_MODERATE,
    CONDUCT_SEVERITY_SEVERE,
    GROUP_COMPETITOR,
)
from behaviors.admin import ConductCategoryAdmin, ConductItemAdmin, ConductRecordAdmin, ConductSeverityRuleAdmin
from behaviors.models import ConductCategory, ConductItem, ConductRecord, ConductSeverityRule, ConductSummary


User = get_user_model()


class ConductItemValidationTestCase(TestCase):
    """奖惩事项默认分值应严格匹配分类性质。"""

    def setUp(self):
        self.reward_category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_REWARD,
            name='奖励分类',
        )
        self.penalty_category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_PENALTY,
            name='惩罚分类',
        )

    def test_reward_item_default_score_must_be_positive(self):
        item = ConductItem(
            category=self.reward_category,
            name='奖励事项',
            default_score=Decimal('0.00'),
        )

        with self.assertRaises(ValidationError) as context:
            item.full_clean()

        self.assertIn('default_score', context.exception.message_dict)

    def test_penalty_item_default_score_must_be_negative(self):
        item = ConductItem(
            category=self.penalty_category,
            name='惩罚事项',
            default_score=Decimal('0.00'),
        )

        with self.assertRaises(ValidationError) as context:
            item.full_clean()

        self.assertIn('default_score', context.exception.message_dict)


class ConductDefaultFixtureTestCase(TestCase):
    """默认 fixture 应提供代表性的奖惩分类与事项。"""

    fixtures = ['behaviors/default']

    def test_default_fixture_seeds_representative_categories_and_items(self):
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


class ConductSeverityRuleValidationTestCase(TestCase):
    """严重程度规则应使用非负系数。"""

    def test_multiplier_cannot_be_negative(self):
        rule = ConductSeverityRule(
            nature=CONDUCT_NATURE_REWARD,
            severity=CONDUCT_SEVERITY_MODERATE,
            multiplier=Decimal('-1.00'),
        )

        with self.assertRaises(ValidationError) as context:
            rule.full_clean()

        self.assertIn('multiplier', context.exception.message_dict)

    def test_zero_multiplier_is_allowed(self):
        rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_PENALTY,
            severity=CONDUCT_SEVERITY_MINOR,
        )

        rule.full_clean()

    def test_severity_labels_are_mapped_by_nature(self):
        reward_rule = ConductSeverityRule(
            nature=CONDUCT_NATURE_REWARD,
            severity=CONDUCT_SEVERITY_MODERATE,
            multiplier=Decimal('1.00'),
        )
        penalty_rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_PENALTY,
            severity=CONDUCT_SEVERITY_MODERATE,
        )

        self.assertEqual(reward_rule.severity_label, '表扬')
        self.assertEqual(penalty_rule.severity_label, '一般')


class ConductRecordValidationTestCase(TestCase):
    """奖惩记录应遵守选手范围与审核状态流。"""

    def setUp(self):
        self.competitor_group = Group.objects.create(name=GROUP_COMPETITOR)
        self.student = User.objects.create_user(username='student', password='testpass123')
        self.student.groups.add(self.competitor_group)
        self.outsider = User.objects.create_user(username='outsider', password='testpass123')
        self.recorder = User.objects.create_user(username='recorder', password='testpass123')
        self.reviewer = User.objects.create_user(username='reviewer', password='testpass123')

        self.category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_REWARD,
            name='学习表现',
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=CONDUCT_SEVERITY_MODERATE,
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
        )
        self.item = ConductItem.objects.create(
            category=self.category,
            name='课堂表现优秀',
            default_score=Decimal('5.00'),
        )

    def test_record_requires_competitor_student(self):
        record = ConductRecord(
            student=self.outsider,
            item=self.item,
            severity=CONDUCT_SEVERITY_MODERATE,
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
            severity=CONDUCT_SEVERITY_MODERATE,
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
            severity=CONDUCT_SEVERITY_MODERATE,
            reason='上传奖惩附件',
            recorded_by=self.recorder,
            attachment=SimpleUploadedFile('evidence.pdf', b'%PDF-1.4\nbehavior test', content_type='application/pdf'),
        )
        self.addCleanup(record.attachment.delete, False)

        self.assertTrue(record.attachment.name.startswith('behaviors/'))
        self.assertEqual(Path(record.attachment.path).parent.parent.name, 'behaviors')

    def test_record_requires_configured_severity_rule(self):
        ConductSeverityRule.objects.filter(
            nature=CONDUCT_NATURE_REWARD,
            severity=CONDUCT_SEVERITY_SEVERE,
        ).delete()

        record = ConductRecord(
            student=self.student,
            item=self.item,
            severity=CONDUCT_SEVERITY_SEVERE,
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
            severity=CONDUCT_SEVERITY_MODERATE,
            reason='需要驳回',
            recorded_by=self.recorder,
            status=ConductRecord.STATUS_REJECTED,
        )

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn('review_note', context.exception.message_dict)

    def test_pending_record_cannot_store_review_metadata(self):
        record = ConductRecord(
            student=self.student,
            item=self.item,
            severity=CONDUCT_SEVERITY_MODERATE,
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
            severity=CONDUCT_SEVERITY_MODERATE,
            reason='先通过再尝试改状态',
            recorded_by=self.recorder,
            status=ConductRecord.STATUS_APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

        record.status = ConductRecord.STATUS_REJECTED
        record.review_note = '再次驳回'

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn('status', context.exception.message_dict)


class ConductSummarySynchronizationTestCase(TestCase):
    """默认分值与严重程度系数变更后，汇总应自动重算。"""

    def setUp(self):
        competitor_group = Group.objects.create(name=GROUP_COMPETITOR)
        self.student = User.objects.create_user(username='summary-student', password='testpass123')
        self.student.groups.add(competitor_group)
        self.recorder = User.objects.create_user(username='summary-recorder', password='testpass123')
        self.reviewer = User.objects.create_user(username='summary-reviewer', password='testpass123')

        self.category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_REWARD,
            name='竞赛荣誉',
        )
        self.rule, _ = ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=CONDUCT_SEVERITY_MODERATE,
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
        )
        self.item = ConductItem.objects.create(
            category=self.category,
            name='获奖',
            default_score=Decimal('5.00'),
        )
        ConductRecord.objects.create(
            student=self.student,
            item=self.item,
            severity=CONDUCT_SEVERITY_MODERATE,
            reason='获奖一次',
            recorded_by=self.recorder,
            status=ConductRecord.STATUS_APPROVED,
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
        competitor_group = Group.objects.create(name=GROUP_COMPETITOR)
        student = User.objects.create_user(username='warning-student', password='testpass123')
        student.groups.add(competitor_group)
        recorder = User.objects.create_user(username='warning-recorder', password='testpass123')
        reviewer = User.objects.create_user(username='warning-reviewer', password='testpass123')

        category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_PENALTY,
            name='纪律问题',
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_PENALTY,
            severity=CONDUCT_SEVERITY_MINOR,
            defaults={'multiplier': Decimal('0.00'), 'order': 10},
        )
        item = ConductItem.objects.create(
            category=category,
            name='迟到',
            default_score=Decimal('-2.00'),
        )

        ConductRecord.objects.create(
            student=student,
            item=item,
            severity=CONDUCT_SEVERITY_MINOR,
            reason='只做警告，不扣分',
            recorded_by=recorder,
            status=ConductRecord.STATUS_APPROVED,
            reviewed_by=reviewer,
            reviewed_at=timezone.now(),
        )

        summary = ConductSummary.objects.get(student=student)
        self.assertEqual(summary.total_score, Decimal('0.00'))
        self.assertEqual(summary.penalty_count, 1)
        self.assertEqual(summary.reward_count, 0)


class ConductRecordAdminTestCase(TestCase):
    """仅保留后台时，admin 仍需区分录入与审核权限。"""

    def setUp(self):
        competitor_group = Group.objects.create(name=GROUP_COMPETITOR)
        self.student = User.objects.create_user(username='admin-student', password='testpass123')
        self.student.groups.add(competitor_group)

        self.recorder = User.objects.create_user(username='admin-recorder', password='testpass123')
        self.other_recorder = User.objects.create_user(username='admin-recorder-2', password='testpass123')
        self.reviewer = User.objects.create_user(username='admin-reviewer', password='testpass123')

        self.recorder.user_permissions.add(Permission.objects.get(codename='add_conduct_record'))
        self.other_recorder.user_permissions.add(Permission.objects.get(codename='add_conduct_record'))
        self.reviewer.user_permissions.add(Permission.objects.get(codename='review_conduct_record'))

        category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_REWARD,
            name='后台测试分类',
        )
        ConductSeverityRule.objects.update_or_create(
            nature=CONDUCT_NATURE_REWARD,
            severity=CONDUCT_SEVERITY_MODERATE,
            defaults={'multiplier': Decimal('1.00'), 'order': 20},
        )
        item = ConductItem.objects.create(
            category=category,
            name='后台测试事项',
            default_score=Decimal('6.00'),
        )
        self.record = ConductRecord.objects.create(
            student=self.student,
            item=item,
            severity=CONDUCT_SEVERITY_MODERATE,
            reason='待审核记录',
            recorded_by=self.recorder,
        )
        self.other_record = ConductRecord.objects.create(
            student=self.student,
            item=item,
            severity=CONDUCT_SEVERITY_MODERATE,
            reason='其他人录入的记录',
            recorded_by=self.other_recorder,
        )

        self.factory = RequestFactory()
        self.admin = ConductRecordAdmin(ConductRecord, AdminSite())
        self.category_admin = ConductCategoryAdmin(ConductCategory, AdminSite())
        self.item_admin = ConductItemAdmin(ConductItem, AdminSite())
        self.rule_admin = ConductSeverityRuleAdmin(ConductSeverityRule, AdminSite())
        self.penalty_category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_PENALTY,
            name='后台惩罚分类',
        )
        self.penalty_item = ConductItem.objects.create(
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

        self.assertEqual(choices[CONDUCT_SEVERITY_MODERATE], '表扬')

    def test_add_record_form_shows_placeholder_before_item_selection(self):
        form_class = self.admin.get_form(self.build_request(self.recorder))
        form = form_class()

        self.assertEqual(list(form.fields['severity'].choices), [('', '请先选择奖惩事项')])

    def test_record_admin_form_includes_dynamic_severity_refresh_url(self):
        form_class = self.admin.get_form(self.build_request(self.recorder))
        form = form_class()

        self.assertIn('data-severity-choices-url', str(form['item']))
        self.assertIn('data-default-severity', str(form['severity']))
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

        self.assertEqual(choices[CONDUCT_SEVERITY_MODERATE], '表扬')

    def test_severity_choices_endpoint_returns_penalty_labels(self):
        request = self.factory.get(
            '/admin/behaviors/conductrecord/severity-choices/',
            {'item_id': self.penalty_item.pk},
        )
        request.user = self.recorder

        response = self.admin.severity_choices_view(request)
        payload = json.loads(response.content)
        choices = {choice['value']: choice['label'] for choice in payload['choices']}

        self.assertEqual(choices[CONDUCT_SEVERITY_MINOR], CONDUCT_PENALTY_SEVERITY_NAMES[CONDUCT_SEVERITY_MINOR])
        self.assertEqual(choices[CONDUCT_SEVERITY_MODERATE], CONDUCT_PENALTY_SEVERITY_NAMES[CONDUCT_SEVERITY_MODERATE])

    def test_rule_admin_form_uses_penalty_specific_severity_labels(self):
        penalty_rule = ConductSeverityRule.objects.get(
            nature=CONDUCT_NATURE_PENALTY,
            severity=CONDUCT_SEVERITY_MODERATE,
        )
        form_class = self.rule_admin.get_form(self.build_request(self.reviewer), penalty_rule)
        form = form_class(instance=penalty_rule)
        choices = dict(form.fields['severity'].choices)

        self.assertEqual(choices[CONDUCT_SEVERITY_MODERATE], '一般')

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
        record.status = ConductRecord.STATUS_APPROVED
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
        self.record.status = ConductRecord.STATUS_APPROVED
        self.record.reviewed_by = self.reviewer
        self.record.reviewed_at = timezone.now()
        self.record.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        self.assertFalse(
            self.admin.has_change_permission(
                self.build_request(self.reviewer),
                self.record,
            )
        )


class ConductUrlTests(TestCase):
    def test_conduct_record_list_is_mounted_at_app_root(self):
        self.assertEqual(reverse('behaviors:conductrecord_list'), '/behaviors/')


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
            nature=CONDUCT_NATURE_REWARD,
            name='审计奖励分类',
        )

    def build_request(self, user):
        request = self.factory.get('/admin/behaviors/')
        request.user = user
        return request

    def test_category_admin_tracks_creator_and_updater(self):
        category = ConductCategory(
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
            severity=CONDUCT_SEVERITY_MODERATE,
        ).delete()

        rule = ConductSeverityRule(
            nature=CONDUCT_NATURE_REWARD,
            severity=CONDUCT_SEVERITY_MODERATE,
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