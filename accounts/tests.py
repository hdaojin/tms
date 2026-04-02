from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AccountHomeTestCase(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='account-user',
			password='testpass123',
		)
		self.client.force_login(self.user)

	def test_account_home_hides_conduct_section(self):
		response = self.client.get(reverse('accounts:home'))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, '学生奖惩管理')
		self.assertNotContains(response, '>奖惩<', html=False)

	def test_conduct_root_is_not_accessible(self):
		response = self.client.get('/conduct/')

		self.assertEqual(response.status_code, 404)
