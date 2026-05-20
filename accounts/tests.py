from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.admin_forms import GroupPermissionBundleAdminForm, UserPermissionBundleAdminForm
from accounts.models import UserProfile
from accounts.services.permission_bundles import sync_group_permission_bundles, sync_user_permission_bundles
from accounts.services.users import get_user_display_name, get_user_full_info
from behaviors.models import ConductSummary
from core.constants import GROUP_COMPETITOR

User = get_user_model()


class UserDisplayNameServiceTests(TestCase):
	def test_display_name_prefers_joined_last_and_first_name(self):
		user = User.objects.create_user(
			username='display-user',
			password='testpass123',
			first_name='三',
			last_name='张',
		)

		self.assertEqual(get_user_display_name(user), '张三')
		self.assertEqual(user.display_name, '张三')

	def test_display_name_falls_back_to_username(self):
		user = User.objects.create_user(
			username='display-user',
			password='testpass123',
		)

		self.assertEqual(get_user_display_name(user), 'display-user')
		self.assertEqual(user.display_name, 'display-user')

	def test_full_info_appends_username_when_name_exists(self):
		user = User.objects.create_user(
			username='student001',
			password='testpass123',
			first_name='三',
			last_name='张',
		)

		self.assertEqual(get_user_full_info(user), '张三(student001)')
		self.assertEqual(user.full_info, '张三(student001)')

	def test_full_info_returns_username_when_name_missing(self):
		user = User.objects.create_user(
			username='student001',
			password='testpass123',
		)

		self.assertEqual(get_user_full_info(user), 'student001')
		self.assertEqual(user.full_info, 'student001')


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

	def test_legacy_conduct_root_is_not_accessible(self):
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


class PermissionBundleSyncServiceTests(TestCase):
	def test_sync_group_permission_bundles_records_codes_and_preserves_extra_permissions(self):
		group = Group.objects.create(name='奖惩录入组')
		extra_permission = Permission.objects.get(codename='review_conduct_record')

		sync_group_permission_bundles(group, ['behaviors.record_conduct'], [extra_permission])

		group.refresh_from_db()
		self.assertEqual(group.profile.selected_permission_bundles, ['behaviors.record_conduct'])
		self.assertSetEqual(
			set(group.permissions.values_list('codename', flat=True)),
			{
				'add_conduct_record',
				'review_conduct_record',
				'view_all_conduct_records',
				'view_conductrecord',
				'view_conductsummary',
			},
		)

	def test_sync_user_permission_bundles_records_codes_and_preserves_extra_permissions(self):
		user = User.objects.create_user('bundle-user', password='testpass123')
		extra_permission = Permission.objects.get(codename='view_all_profiles')

		sync_user_permission_bundles(user, ['traininglogs.upload_traininglog'], [extra_permission])

		user.refresh_from_db()
		self.assertEqual(user.profile.selected_permission_bundles, ['traininglogs.upload_traininglog'])
		self.assertSetEqual(
			set(user.user_permissions.values_list('codename', flat=True)),
			{
				'add_traininglog',
				'view_traininglog',
				'view_all_profiles',
			},
		)

	def test_sync_group_permission_bundles_for_traininglog_view_all_grants_all_view_permissions(self):
		group = Group.objects.create(name='训练日志全看组')

		sync_group_permission_bundles(group, ['traininglogs.view_all_traininglogs'])

		group.refresh_from_db()
		self.assertEqual(group.profile.selected_permission_bundles, ['traininglogs.view_all_traininglogs'])
		self.assertSetEqual(
			set(group.permissions.values_list('codename', flat=True)),
			{
				'view_all_traininglog',
				'view_coach_traininglog',
				'view_competitor_traininglog',
				'view_traininglog',
			},
		)


class PermissionBundleAdminFormTests(TestCase):
	def test_group_admin_form_only_shows_extra_permissions(self):
		group = Group.objects.create(name='表单测试组')
		extra_permission = Permission.objects.get(codename='review_conduct_record')
		sync_group_permission_bundles(group, ['behaviors.record_conduct'], [extra_permission])

		form = GroupPermissionBundleAdminForm(instance=group)

		self.assertEqual(form.initial['selected_permission_bundles'], ['behaviors.record_conduct'])
		self.assertQuerySetEqual(
			form.fields['permissions'].initial.order_by('pk'),
			Permission.objects.filter(pk=extra_permission.pk),
			transform=lambda permission: permission,
		)

	def test_user_admin_form_only_shows_extra_permissions(self):
		user = User.objects.create_user('form-user', password='testpass123')
		extra_permission = Permission.objects.get(codename='view_all_profiles')
		sync_user_permission_bundles(user, ['traininglogs.upload_traininglog'], [extra_permission])

		form = UserPermissionBundleAdminForm(instance=user)

		self.assertEqual(form.initial['selected_permission_bundles'], ['traininglogs.upload_traininglog'])
		self.assertQuerySetEqual(
			form.fields['user_permissions'].initial.order_by('pk'),
			Permission.objects.filter(pk=extra_permission.pk),
			transform=lambda permission: permission,
		)


class PermissionBundleAdminPageTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_superuser('permission-admin', password='testpass123')
		self.client.force_login(self.admin)

	def test_group_admin_change_page_shows_business_permission_bundle_field(self):
		group = Group.objects.create(name='后台权限组')

		response = self.client.get(reverse('admin:auth_group_change', args=[group.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '业务权限包')
		self.assertContains(response, '额外原生权限')

	def test_user_admin_change_page_shows_business_permission_bundle_field(self):
		user = User.objects.create_user('page-user', password='testpass123')

		response = self.client.get(reverse('admin:auth_user_change', args=[user.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '业务权限包')
		self.assertContains(response, '额外原生权限')


class PermissionBundleBackfillCommandTests(TestCase):
	def test_command_preview_does_not_write_profiles(self):
		group = Group.objects.create(name='预检查组')
		group.permissions.add(
			Permission.objects.get(codename='add_traininglog'),
			Permission.objects.get(codename='view_traininglog'),
		)

		output = StringIO()
		call_command('backfill_permission_bundles', stdout=output)

		self.assertFalse(hasattr(group, 'profile'))
		self.assertIn('用户组 预检查组: 业务权限包 -> traininglogs.upload_traininglog', output.getvalue())
		self.assertIn('以上为预检查结果', output.getvalue())

	def test_command_execute_backfills_group_and_user_bundles(self):
		group = Group.objects.create(name='训练日志组')
		group.permissions.add(
			Permission.objects.get(codename='add_traininglog'),
			Permission.objects.get(codename='view_traininglog'),
		)

		user = User.objects.create_user('bundle-backfill-user', password='testpass123')
		user.user_permissions.add(
			Permission.objects.get(codename='add_conduct_record'),
			Permission.objects.get(codename='review_conduct_record'),
			Permission.objects.get(codename='view_all_conduct_records'),
			Permission.objects.get(codename='view_conductrecord'),
			Permission.objects.get(codename='view_conductsummary'),
		)

		output = StringIO()
		call_command('backfill_permission_bundles', '--execute', stdout=output)

		group.refresh_from_db()
		user.refresh_from_db()
		self.assertEqual(group.profile.selected_permission_bundles, ['traininglogs.upload_traininglog'])
		self.assertEqual(
			user.profile.selected_permission_bundles,
			['behaviors.record_conduct', 'behaviors.review_conduct'],
		)
		self.assertSetEqual(
			set(user.user_permissions.values_list('codename', flat=True)),
			{
				'add_conduct_record',
				'review_conduct_record',
				'view_all_conduct_records',
				'view_conductrecord',
				'view_conductsummary',
			},
		)
		self.assertIn('已回填 2 个对象的业务权限包。', output.getvalue())
