from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core.constants import (
    CONDUCT_NATURE_PENALTY,
    CONDUCT_NATURE_REWARD,
    CONDUCT_NATURE_WARNING,
    GROUP_COMPETITOR,
)
from conduct.admin import ConductRecordAdmin
from conduct.models import ConductCategory, ConductItem, ConductRecord, ConductSummary


User = get_user_model()


class ConductItemValidationTestCase(TestCase):
    """奖惩事项分值应严格匹配分类性质。"""

    def setUp(self):
        self.reward_category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_REWARD,
            name='奖励分类',
        )
        self.penalty_category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_PENALTY,
            name='惩罚分类',
        )
        self.warning_category = ConductCategory.objects.create(
            nature=CONDUCT_NATURE_WARNING,
            name='警告分类',
        )

    def test_item_score_must_match_category_nature(self):
        invalid_cases = [
            (self.reward_category, Decimal('0.00')),
            (self.penalty_category, Decimal('0.00')),
            (self.warning_category, Decimal('1.00')),
        ]

        for index, (category, score) in enumerate(invalid_cases, start=1):
            with self.subTest(case=index, category=category.name, score=score):
                item = ConductItem(category=category, name=f'事项{index}', score=score)
                with self.assertRaises(ValidationError) as context:
                    item.full_clean()

                self.assertIn('score', context.exception.message_dict)


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
        self.item = ConductItem.objects.create(
            category=self.category,
            name='课堂表现优秀',
            score=Decimal('5.00'),
        )

    def test_record_requires_competitor_student(self):
        record = ConductRecord(
            student=self.outsider,
            item=self.item,
            reason='非选手用户不应被录入',
            recorded_by=self.recorder,
        )

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn('student', context.exception.message_dict)

    def test_rejected_record_requires_review_note(self):
        record = ConductRecord(
            student=self.student,
            item=self.item,
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
    """动态分值语义下，事项变更后汇总应自动重算。"""

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
        self.item = ConductItem.objects.create(
            category=self.category,
            name='获奖',
            score=Decimal('5.00'),
        )
        ConductRecord.objects.create(
            student=self.student,
            item=self.item,
            reason='获奖一次',
            recorded_by=self.recorder,
            status=ConductRecord.STATUS_APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

    def test_item_score_change_recalculates_summary(self):
        summary = ConductSummary.objects.get(student=self.student)
        self.assertEqual(summary.total_score, Decimal('5.00'))

        self.item.score = Decimal('8.00')
        self.item.save()

        summary.refresh_from_db()
        self.assertEqual(summary.total_score, Decimal('8.00'))
        self.assertEqual(summary.reward_count, 1)
        self.assertEqual(summary.penalty_count, 0)


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
        item = ConductItem.objects.create(
            category=category,
            name='后台测试事项',
            score=Decimal('6.00'),
        )
        self.record = ConductRecord.objects.create(
            student=self.student,
            item=item,
            reason='待审核记录',
            recorded_by=self.recorder,
        )
        self.other_record = ConductRecord.objects.create(
            student=self.student,
            item=item,
            reason='其他人录入的记录',
            recorded_by=self.other_recorder,
        )

        self.factory = RequestFactory()
        self.admin = ConductRecordAdmin(ConductRecord, AdminSite())

    def build_request(self, user):
        request = self.factory.get('/admin/conduct/conductrecord/')
        request.user = user
        return request

    def test_recorder_queryset_only_contains_own_records(self):
        queryset = self.admin.get_queryset(self.build_request(self.recorder))

        self.assertQuerySetEqual(
            queryset.order_by('pk').values_list('pk', flat=True),
            [self.record.pk],
            transform=lambda value: value,
        )

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
        self.assertEqual(summary.total_score, Decimal('6.00'))

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