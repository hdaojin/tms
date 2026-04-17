from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from conduct.models import ConductSummary
from core.constants import GROUP_COMPETITOR

User = get_user_model()


class AccountHomeTestCase(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='account-user',
			password='testpass123',
		)
		self.client.force_login(self.user)

	def test_account_home_shows_conduct_section(self):
		response = self.client.get(reverse('accounts:home'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '奖惩')

	def test_conduct_root_is_not_accessible(self):
		response = self.client.get('/conduct/')

		self.assertEqual(response.status_code, 404)


class UserAdminDeleteTest(TestCase):
	def setUp(self):
		self.admin = User.objects.create_superuser('admin', password='testpass')
		self.student = User.objects.create_user('student', password='testpass')
		ConductSummary.objects.create(student=self.student)
		self.client.force_login(self.admin)

	def test_delete_user_with_conduct_summary_shows_confirmation(self):
		"""删除用户时，ConductSummary 不应阻止权限检查"""
		url = reverse('admin:auth_user_delete', args=[self.student.pk])
		resp = self.client.get(url)
		self.assertEqual(resp.status_code, 200)
		self.assertContains(resp, '奖惩汇总')
		self.assertNotContains(resp, 'permissions to delete')

	def test_delete_user_cascades_conduct_summary(self):
		"""删除用户后，关联的 ConductSummary 也被级联删除"""
		url = reverse('admin:auth_user_delete', args=[self.student.pk])
		self.client.post(url, {'post': 'yes'})
		self.assertFalse(User.objects.filter(pk=self.student.pk).exists())
		self.assertFalse(ConductSummary.objects.filter(student=self.student).exists())


class UserListTableTemplateRegressionTest(TestCase):
	def setUp(self):
		self.admin = User.objects.create_superuser('table-admin', password='testpass123')
		self.competitor_group, _ = Group.objects.get_or_create(name=GROUP_COMPETITOR)

		for index in range(1, 22):
			user = User.objects.create_user(
				username=f'competitor-{index:02d}',
				password='testpass123',
				first_name=f'选手{index:02d}',
			)
			user.groups.add(self.competitor_group)
			UserProfile.objects.create(
				user=user,
				join_date=date(2026, 4, min(index, 28)),
			)

		self.client.force_login(self.admin)

	def test_user_list_renders_without_template_syntax_error_and_shows_pagination(self):
		response = self.client.get(reverse('accounts:user_list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '选手01')
		self.assertContains(response, '?page=2')
