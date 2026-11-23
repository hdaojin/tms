import json
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from standards.models import SkillProject
from training.models import TrainingCycle, TrainingCycleMember
from .models import (
    ConductCategory, ConductCycleAssignment, ConductItem, ConductPolicy, ConductRecord, ConductSeverityRule,
)


class CycleConductTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_superuser(username='cycle-admin')
        cls.operator = users.create_user(username='cycle-operator', first_name='教练')
        cls.student = users.create_user(username='cycle-student', first_name='学员甲')
        cls.other_student = users.create_user(username='cycle-other', first_name='学员乙')
        project = SkillProject.objects.create(code='conduct', name='奖惩测试项目')
        today = timezone.localdate()
        cls.cycle = TrainingCycle.objects.create(code='c1', name='第一周期', start_date=today, skill_project=project)
        cls.other_cycle = TrainingCycle.objects.create(code='c2', name='第二周期', start_date=today, skill_project=project)
        for user in (cls.student, cls.other_student):
            TrainingCycleMember.objects.create(training_cycle=cls.cycle, user=user, role='competitor')
        cls.operator.user_permissions.add(*Permission.objects.filter(codename__in=[
            'add_conduct_record', 'review_conduct_record', 'change_conductpolicy',
        ], content_type__app_label='behaviors'))
        ConductCycleAssignment.objects.create(cycle=cls.cycle, user=cls.operator, can_enter=True, can_review=True)

    def url(self, name, *args):
        return reverse(f'behaviors:cycle_{name}', args=args or [self.cycle.pk])

    def make_draft(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url('elite_draft'))
        self.assertEqual(response.status_code, 302)
        draft = ConductPolicy.objects.get(cycle=self.cycle)
        self.assertEqual(draft.rules.filter(section='competition').count(), 15)
        self.assertEqual(draft.rules.filter(section='management').count(), 36)
        self.assertEqual(draft.rules.filter(section='learning').count(), 7)
        self.assertEqual(draft.rules.get(policy_item__item__name='学校表彰').points, Decimal('10.00'))
        self.assertEqual(draft.rules.get(condition='排名第一').points, Decimal('7.00'))
        source = json.loads(Path(__file__).with_name('elite_class_policy.json').read_text(encoding='utf-8'))
        original = Counter(
            (row['category'], row['item'], row['section'], row['condition'], Decimal(row['points']), row['unit'])
            for row in source['rules']
        )
        converted = Counter(
            (rule.policy_item.item.category.name, rule.policy_item.item.name, rule.section,
             rule.condition, rule.points, rule.unit)
            for rule in draft.rules.select_related('policy_item__item__category')
        )
        self.assertEqual(converted, original)
        return draft

    def publish(self, draft):
        self.client.force_login(self.admin)
        draft.refresh_from_db()
        response = self.client.post(self.url('policy', self.cycle.pk, draft.pk), {
            'revision': draft.updated_at.isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        draft.refresh_from_db()
        self.assertIsNotNone(draft.published_at)

    def test_draft_publication_preview_multi_entry_review_void_and_scope(self):
        media = self.enterContext(TemporaryDirectory())
        self.enterContext(self.settings(PRIVATE_MEDIA_ROOT=media, FILE_UPLOAD_MAX_MEMORY_SIZE=1))
        draft = self.make_draft()
        self.assertContains(self.client.get(reverse('behaviors:policy_rules', args=[self.cycle.pk, draft.pk])), '宿舍管理')
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url('policy', self.cycle.pk, draft.pk)).status_code, 404)
        self.assertEqual(self.client.get(self.url('detail', self.other_cycle.pk)).status_code, 404)
        self.publish(draft)
        self.client.force_login(self.student)
        self.assertContains(self.client.get(self.url('policy', self.cycle.pk, draft.pk)), '精英班每周作息')
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(self.url('entry', self.other_cycle.pk)).status_code, 403)
        self.assertContains(self.client.get(self.url('entry')), '按日期加载计分规则')
        rule = draft.rules.get(condition='病假（以0.5天为单位）')
        payload = {
            'occurred_date': timezone.localdate().isoformat(),
            'students': [self.student.pk, self.other_student.pk],
            'rule': rule.pk, 'quantity': 3, 'reason': '病假一天半',
        }
        preview = self.client.post(self.url('entry'), payload)
        self.assertContains(preview, '确认本次奖惩')
        self.assertContains(preview, '-1.50')
        self.assertFalse(ConductRecord.objects.exists())
        confirmation = preview.context['form'].initial['confirmation']
        response = self.client.post(self.url('entry'), {
            **payload, 'confirmation': confirmation, 'action': 'confirm',
            'attachment': SimpleUploadedFile('evidence.pdf', b'%PDF-1.7\n', content_type='application/pdf'),
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.post(self.url('entry'), {
            **payload, 'confirmation': confirmation, 'action': 'confirm',
            'attachment': SimpleUploadedFile('evidence.pdf', b'%PDF-1.7\n', content_type='application/pdf'),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ConductRecord.objects.count(), 2)
        for entry in ConductRecord.objects.all():
            with entry.attachment.open('rb') as evidence:
                self.assertEqual(evidence.read(), b'%PDF-1.7\n')
        record = ConductRecord.objects.get(student=self.student)
        self.assertEqual(record.frozen_points, Decimal('-1.50'))
        ConductRecord.objects.filter(pk=record.pk).update(source_cycle_record_id=1000)
        self.assertRedirects(
            self.client.get(self.url('record', self.cycle.pk, 1000)),
            reverse('behaviors:record_detail', args=[record.pk]),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(self.url('attachment', self.cycle.pk, 1000)),
            reverse('behaviors:conduct_attachment', args=[record.pk]),
            fetch_redirect_response=False,
        )
        self.client.post(reverse('behaviors:record_detail', args=[record.pk]), {
            'action': 'approve', 'revision': record.updated_at.isoformat(),
        })
        record.refresh_from_db()
        self.assertEqual(record.status, ConductRecord.Status.APPROVED)
        self.assertEqual(record.reviewed_by, self.operator)
        self.client.force_login(self.student)
        summary = self.client.get(reverse('behaviors:conductsummary_list'))
        self.assertTemplateUsed(summary, 'django_tables2/tms.html')
        self.assertContains(summary, '-1.50')
        other = ConductRecord.objects.get(student=self.other_student)
        self.assertEqual(self.client.get(reverse('behaviors:record_detail', args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('behaviors:conduct_attachment', args=[other.pk])).status_code, 404)
        self.client.force_login(self.operator)
        self.client.post(reverse('behaviors:record_detail', args=[record.pk]), {
            'action': 'void', 'note': '录入对象错误', 'revision': record.updated_at.isoformat(),
        })
        record.refresh_from_db()
        self.assertEqual(record.status, ConductRecord.Status.VOID)
        self.assertEqual(record.reviewed_by, self.operator)
        self.client.force_login(self.student)
        summary = self.client.get(reverse('behaviors:conductsummary_list'))
        self.assertNotContains(summary, '-1.50')
        self.assertContains(summary, '暂无数据')

    def test_later_policy_uses_its_own_effective_date_and_frozen_labels(self):
        draft = self.make_draft()
        self.publish(draft)
        rule = draft.rules.get(condition='病假（以0.5天为单位）')
        item = rule.policy_item.item
        item.name = '调整后的目录名'
        item.save()
        response = self.client.post(self.url('policy_new') + f'?copy={draft.pk}', {
            'title': '第二版', 'issuer': draft.issuer, 'body': draft.body,
            'effective_date': (timezone.localdate() + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        later = ConductPolicy.objects.get(title='第二版')
        self.assertEqual(later.rules.count(), draft.rules.count())
        self.publish(later)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url('policy', self.cycle.pk, later.pk)).status_code, 404)
        self.assertContains(self.client.get(reverse('behaviors:policy_rules', args=[self.cycle.pk, draft.pk])), '病假（以0.5天为单位）')
        self.assertNotContains(self.client.get(reverse('behaviors:policy_rules', args=[self.cycle.pk, draft.pk])), '调整后的目录名')

    def test_catalog_lists_hierarchy_and_requires_independent_global_permission(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('behaviors:category_new'), {
            'nature': 'REWARD', 'code': 'cycle-reward', 'name': '训练奖励',
            'description': '奖励分类', 'order': 0, 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        category = ConductCategory.objects.get(code='cycle-reward')
        response = self.client.post(reverse('behaviors:item_new', args=[category.pk]), {
            'category': 999, 'code': 'progress', 'name': '训练进步', 'default_score': '2.25', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        item = ConductItem.objects.get(category=category)
        self.assertEqual(item.default_score, Decimal('2.25'))
        list_url = reverse('behaviors:catalog_items', args=[category.pk])
        self.assertContains(self.client.get(reverse('behaviors:catalog_categories')), list_url)
        self.assertContains(self.client.get(list_url), '训练进步')
        self.assertContains(self.client.get(response.url), '训练进步')
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(list_url).status_code, 403)
        old_permission = Permission.objects.get(codename='change_conductcatalog')
        self.operator.user_permissions.add(old_permission)
        self.assertEqual(self.client.get(list_url).status_code, 403)
        self.operator.user_permissions.add(Permission.objects.get(codename='manage_global_conduct_catalog'))
        self.assertEqual(self.client.get(list_url).status_code, 200)

    def test_unassigned_pending_record_shares_ledger_and_only_superuser_can_review(self):
        category = ConductCategory.objects.create(code='past', name='旧目录', nature='PENALTY')
        item = ConductItem.objects.create(category=category, code='past', name='旧事项', default_score=Decimal('-1.25'))
        old = ConductRecord.objects.create(
            student=self.student, item=item, item_label=item.name, category_label=category.name,
            severity_label='一般', frozen_nature='PENALTY', frozen_points=Decimal('-1.2345'), reason='旧记录',
        )
        read = Permission.objects.get(codename='view_conductrecord')
        self.student.user_permissions.add(read)
        self.operator.user_permissions.add(read)
        detail = reverse('behaviors:record_detail', args=[old.pk])
        payload = {'action': 'approve', 'revision': old.updated_at.isoformat()}

        self.client.force_login(self.student)
        response = self.client.get(reverse('behaviors:conductrecord_list'), {'cycle': 'unassigned'})
        self.assertContains(response, '旧事项')
        self.assertContains(response, '-1.2345')
        self.assertNotContains(response, '历史奖惩记录')
        self.assertContains(self.client.get(detail), '待审核')
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.post(detail, payload).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(detail, payload).status_code, 302)
        old.refresh_from_db()
        self.assertEqual(old.status, ConductRecord.Status.APPROVED)
        self.assertIsNone(old.cycle_id)
        self.assertEqual(old.frozen_points, Decimal('-1.2345'))
        self.assertContains(self.client.get(reverse('behaviors:conductsummary_list')), '-1.2345')
        with self.assertRaises(ProtectedError):
            self.student.delete()

    def test_legacy_backoffice_recorder_keeps_read_scope_without_new_frontend_access(self):
        self.operator.is_staff = True
        self.operator.save(update_fields=['is_staff'])
        self.operator.user_permissions.remove(Permission.objects.get(codename='review_conduct_record'))
        category = ConductCategory.objects.create(code='admin-past', name='旧分类示例', nature='PENALTY')
        item = ConductItem.objects.create(category=category, code='past', name='旧事项示例', default_score=Decimal('-1'))
        own = ConductRecord.objects.create(
            student=self.student, recorded_by=self.operator, item=item, item_label='本人经办记录',
            frozen_nature='PENALTY', frozen_points=Decimal('-1'), attachment='private.pdf',
        )
        ConductRecord.objects.create(
            student=self.student, recorded_by=self.admin, item=item, item_label='他人经办记录',
            frozen_nature='PENALTY', frozen_points=Decimal('-1'),
        )
        self.client.force_login(self.operator)
        backoffice = self.client.get(reverse('admin:behaviors_conductrecord_changelist'))
        self.assertContains(backoffice, '本人经办记录')
        self.assertNotContains(backoffice, '他人经办记录')
        detail = self.client.get(reverse('admin:behaviors_conductrecord_change', args=[own.pk]))
        self.assertContains(detail, '本人经办记录')
        self.assertNotContains(detail, '下载附件')
        public = self.client.get(reverse('behaviors:record_detail', args=[own.pk]))
        self.assertEqual(public.status_code, 404)

    def test_global_tier_copies_into_draft_and_zero_points_can_be_recorded(self):
        category = ConductCategory.objects.create(code='discipline', name='纪律', nature='PENALTY')
        item = ConductItem.objects.create(
            category=category, code='notice', name='课堂提醒', default_score=Decimal('-2.50'),
        )
        template = ConductSeverityRule.objects.get(nature='PENALTY', multiplier=Decimal(0))
        self.client.force_login(self.admin)
        draft = ConductPolicy.objects.create(
            cycle=self.cycle, title='条例', issuer='教练组', effective_date=timezone.localdate(),
        )
        response = self.client.post(
            reverse('behaviors:policy_item_new', args=[self.cycle.pk, draft.pk]), {'item': item.pk},
        )
        self.assertEqual(response.status_code, 302)
        group = draft.policy_items.get()
        self.assertEqual(group.base_score, item.default_score)
        response = self.client.post(response.url, {'section': 'management', 'template': template.pk, 'order': 0})
        self.assertEqual(response.status_code, 302)
        rule = draft.rules.get()
        self.assertEqual(rule.condition, template.label)
        self.assertEqual(rule.multiplier, Decimal(0))
        self.publish(draft)

        self.client.post(reverse('behaviors:rate_edit', args=[template.pk]), {
            'label': '更新后名称', 'multiplier': '3.25', 'order': 0, 'is_active': 'on',
        })
        template.refresh_from_db()
        self.assertEqual(template.multiplier, Decimal('3.25'))
        item.default_score = Decimal('-5')
        item.save()
        self.client.force_login(self.operator)
        url = self.url('entry')
        payload = {
            'occurred_date': timezone.localdate().isoformat(), 'students': [self.student.pk],
            'rule': rule.pk, 'quantity': 1, 'reason': '口头提醒',
        }
        preview = self.client.post(url, payload)
        self.assertContains(preview, '确认本次奖惩')
        confirmation = preview.context['form'].initial['confirmation']
        self.assertEqual(self.client.post(url, {**payload, 'confirmation': confirmation, 'action': 'confirm'}).status_code, 302)
        record = ConductRecord.objects.get()
        self.assertEqual(record.frozen_points, Decimal(0))
        self.assertEqual(record.severity_label, rule.condition)
        self.assertEqual(record.rule.policy_item.base_score, Decimal('-2.50'))
