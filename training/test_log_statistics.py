from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.navigation import get_section_items

from .forms import TrainingLogStatisticsForm
from .models import TrainingCycleMember, TrainingLog
from .selectors import training_log_submission_statistics, training_log_statistics_cycles_for
from .tests import TrainingFixtureMixin, User


class TrainingLogStatisticsTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('viewer', last_name='张', first_name='三')
        self.other = User.objects.create_user('coach', last_name='李', first_name='四', is_active=False)
        self.period = self.cycle(start_date=date(2024, 2, 2), end_date=date(2024, 2, 29))
        self.member(self.user)
        self.member(self.other, role='coach')
        self.grant('view_traininglog_statistics')
        self.client.force_login(self.user)
        self.url = reverse('training:monthly_stats')
        self.params = {'cycle': self.period.pk, 'year': 2024, 'month': 2}

    def member(self, user, **kwargs):
        return TrainingCycleMember.objects.create(training_cycle=self.period, user=user,
                                                  **({'role': 'competitor'} | kwargs))

    def grant(self, *codes):
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='training', codename__in=codes))
        for key in ('_perm_cache', '_user_perm_cache', '_group_perm_cache'):
            self.user.__dict__.pop(key, None)

    def log(self, user=None, day=3, cycle=None):
        return TrainingLog.objects.create(training_cycle=cycle or self.period, author=user or self.user,
                                          training_date=date(2024, 2, day), topic='训练日志')

    def stats(self, **kwargs):
        return training_log_submission_statistics(self.user, **({'cycle': self.period, 'year': 2024, 'month': 2} | kwargs))

    def test_permission_required_and_initial_prompt(self):
        response = self.client.get(self.url)
        self.assertContains(response, '请选择训练周期')
        self.assertEqual(response.context['form'].initial['month'], timezone.localdate().month)
        self.user.user_permissions.clear()
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_personal_scope_and_forged_cycle(self):
        self.log()
        self.log(self.other)
        other_cycle = self.cycle(code='PRIVATE')
        response = self.client.get(self.url, self.params)
        self.assertContains(response, '张三')
        self.assertNotContains(response, '李四')
        self.assertNotContains(response, 'PRIVATE')
        self.assertEqual([p['count'] for p in response.context['people']], [1])
        response = self.client.get(self.url, self.params | {'cycle': other_cycle.pk})
        self.assertTrue(response.context['form'].errors)
        self.assertNotIn('rows', response.context)
        self.assertEqual(self.stats(cycle=other_cycle)['people'], [])

    def test_global_scope_roles_inactive_zero_and_backfill(self):
        self.grant('view_all_traininglog')
        zero = User.objects.create_user('zero')
        self.member(zero)
        self.log(self.other)
        other_cycle = self.cycle(code='SECOND')
        self.log(cycle=other_cycle)
        result = self.stats()
        self.assertEqual({p['user_id']: p['count'] for p in result['people']},
                         {self.user.pk: 0, self.other.pk: 1, zero.pk: 0})
        self.log(day=2)
        result = self.stats()
        self.assertEqual(len(result['rows']), 28)
        self.assertEqual(result['rows'][0]['submitted'][0]['name'], '张三')
        self.assertEqual([p['name'] for p in self.stats(role='coach')['people']], ['李四'])
        self.assertEqual(len(self.stats(role='competitor')['people']), 2)

    def test_today_cycle_boundaries_and_future(self):
        self.period.end_date = None
        self.period.save()
        with patch('training.selectors.timezone.localdate', return_value=date(2024, 2, 10)):
            result = self.stats()
            self.assertEqual((result['range_start'], result['range_end']), (date(2024, 2, 2), date(2024, 2, 10)))
            self.assertEqual(self.stats(month=3)['rows'], [])
            self.assertEqual(self.stats(month=1)['rows'], [])
        self.period.end_date = date(2024, 2, 5)
        self.period.save()
        self.assertEqual(self.stats()['range_end'], date(2024, 2, 5))

    def test_invalid_filters_never_return_statistics(self):
        for changes in ({'year': 'x'}, {'year': 0}, {'year': 10000}, {'month': 13},
                        {'month': ''}, {'role': 'admin'}, {'cycle': 'x'}):
            with self.subTest(changes=changes):
                response = self.client.get(self.url, self.params | changes)
                self.assertTrue(response.context['form'].errors)
                self.assertNotIn('rows', response.context)

    def test_detail_links_require_view_permission_and_preserve_filters(self):
        log = self.log()
        detail = reverse('training:log_detail', args=[log.pk])
        self.assertNotContains(self.client.get(self.url, self.params), f'href="{detail}"')
        self.grant('view_traininglog')
        response = self.client.get(self.url, self.params)
        self.assertContains(response, f'href="{detail}"')
        self.assertEqual(response.context['form']['cycle'].value(), str(self.period.pk))
        self.assertContains(self.client.get(detail), '训练日志')

    def test_superuser_and_statistics_permission_scope(self):
        self.user.user_permissions.clear()
        self.assertFalse(training_log_statistics_cycles_for(self.user).exists())
        self.user = User.objects.get(pk=self.user.pk)
        self.user.is_superuser = True
        self.user.save()
        self.assertEqual(len(self.stats()['people']), 2)
        self.assertEqual(self.client.get(self.url, self.params).status_code, 200)

    def test_selector_queries_do_not_grow_with_members_or_days(self):
        self.grant('view_all_traininglog')
        self.log()
        self.user.get_all_permissions()
        with self.assertNumQueries(3):
            self.stats()
        for index in range(8):
            self.member(User.objects.create_user(f'member{index}'))
        self.log(day=4)
        with self.assertNumQueries(3):
            result = self.stats()
        self.assertEqual(len(result['people']), 10)

    def test_form_defaults_and_role_validation(self):
        form = TrainingLogStatisticsForm(self.params | {'role': 'coach'}, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['month'], 2)

    def test_navigation_follows_statistics_permission(self):
        def statistics_entries():
            return [child for group in get_section_items('training', self.user)
                    for child in group.children if child.url_name == 'training:monthly_stats']

        entries = statistics_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].resolved_url, self.url)
        self.user.user_permissions.clear()
        self.user = User.objects.get(pk=self.user.pk)
        self.assertEqual(statistics_entries(), [])

    def test_no_members_and_default_month_parameters(self):
        response = self.client.get(self.url, {'cycle': self.period.pk})
        self.assertFalse(response.context['form'].errors)
        self.assertEqual(response.context['form'].cleaned_data['month'], timezone.localdate().month)
        result = self.stats(role='coach')
        self.assertEqual(result['people'], [])
        self.assertTrue(all(not row['submitted'] and not row['unsubmitted'] for row in result['rows']))
