from datetime import date, datetime
from io import StringIO

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.admin_forms import GroupPermissionBundleAdminForm, UserPermissionBundleAdminForm
from accounts.models import GroupProfile, UserProfile
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

	def test_account_home_section_cards_use_three_column_centered_layout(self):
		response = self.client.get(reverse('accounts:home'))

		self.assertEqual(response.status_code, 200)
		soup = BeautifulSoup(response.content, 'html.parser')
		grid = soup.select_one('.grid.grid-cols-1.gap-6.md\\:grid-cols-2.xl\\:grid-cols-3')
		self.assertIsNotNone(grid)
		card = grid.select_one('a.card')
		self.assertIsNotNone(card)
		for class_name in ['card-border', 'h-full', 'min-h-56', 'border', 'border-base-300', 'shadow']:
			self.assertIn(class_name, card.get('class', []))
		card_body = card.select_one('.card-body')
		for class_name in ['min-h-56', 'items-center', 'justify-center', 'text-center']:
			self.assertIn(class_name, card_body.get('class', []))
		icon = card_body.select_one('span[class*="icon-"]')
		self.assertIsNotNone(icon)
		self.assertIn('size-8', icon.get('class', []))
		title = card_body.select_one('.card-title')
		self.assertIsNotNone(title)
		self.assertIn('text-lg', title.get('class', []))

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
		User.objects.filter(pk=self.admin.pk).update(
			date_joined=datetime(2026, 3, 31, 8, 0, tzinfo=timezone.get_current_timezone())
		)

		for index in range(1, 22):
			user = User.objects.create_user(
				username=f'competitor-{index:02d}',
				password='testpass123',
				first_name=f'选手{index:02d}',
			)
			User.objects.filter(pk=user.pk).update(
				date_joined=datetime(2026, 4, index, 8, 0, tzinfo=timezone.get_current_timezone())
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
		self.assertContains(response, '选手21')
		self.assertContains(response, '?page=2')


class UserListRoleColumnTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_superuser('role-table-admin', password='testpass123')
		self.coach_group = Group.objects.create(name='教练')
		self.competitor_group = Group.objects.create(name=GROUP_COMPETITOR)

		self.coach = User.objects.create_user(
			username='a-coach',
			password='testpass123',
			first_name='教练',
			last_name='李',
		)
		self.coach.groups.add(self.coach_group)
		UserProfile.objects.create(user=self.coach, join_date=date(2026, 6, 1))

		self.multi_role_user = User.objects.create_user(
			username='b-multi-role',
			password='testpass123',
			first_name='多角',
			last_name='张',
		)
		self.multi_role_user.groups.add(self.coach_group, self.competitor_group)
		UserProfile.objects.create(user=self.multi_role_user, join_date=date(2026, 6, 2))

		self.no_role_user = User.objects.create_user(
			username='c-no-role',
			password='testpass123',
			first_name='未分配',
			last_name='赵',
			is_active=False,
		)
		UserProfile.objects.create(user=self.no_role_user, join_date=date(2026, 6, 3))
		User.objects.filter(pk=self.coach.pk).update(
			date_joined=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.get_current_timezone())
		)
		User.objects.filter(pk=self.multi_role_user.pk).update(
			date_joined=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.get_current_timezone())
		)
		User.objects.filter(pk=self.no_role_user.pk).update(
			date_joined=datetime(2026, 6, 3, 8, 0, tzinfo=timezone.get_current_timezone())
		)
		User.objects.filter(pk=self.admin.pk).update(
			date_joined=datetime(2026, 5, 31, 8, 0, tzinfo=timezone.get_current_timezone())
		)
		self.client.force_login(self.admin)

	def test_user_list_shows_all_users_and_role_column_after_name(self):
		response = self.client.get(reverse('accounts:user_list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '李教练')
		self.assertContains(response, '张多角')
		self.assertContains(response, '赵未分配')
		self.assertContains(response, '未分配')

		soup = BeautifulSoup(response.content, 'html.parser')
		headers = [th.get_text(strip=True) for th in soup.select('thead th')]
		self.assertEqual(headers[1:3], ['姓名', '角色'])
		sortable_headers = {a.get_text(strip=True) for a in soup.select('thead th a')}
		self.assertSetEqual(
			sortable_headers,
			{'姓名', '角色', '性别', '出生日期', '入读日期', '离开日期', '激活'},
		)
		roles_column_index = headers.index('角色')
		activation_column_index = headers.index('激活')
		self.assertLess(activation_column_index, headers.index('操作'))

		name_cell = soup.find('td', string='李教练')
		self.assertIsNotNone(name_cell)
		self.assertIn('text-center', name_cell.get('class', []))
		self.assertIn('align-middle', name_cell.get('class', []))

		multi_role_row = soup.find('td', string='张多角').find_parent('tr')
		multi_role_text = multi_role_row.get_text(' ', strip=True)
		self.assertIn('教练', multi_role_text)
		self.assertIn(GROUP_COMPETITOR, multi_role_text)
		multi_role_cells = multi_role_row.find_all('td')
		multi_role_cell = multi_role_cells[roles_column_index]
		coach_badge = multi_role_cell.find('span', string='教练')
		competitor_badge = multi_role_cell.find('span', string=GROUP_COMPETITOR)
		self.assertIn('badge-soft', coach_badge.get('class', []))
		self.assertIn('badge-primary', coach_badge.get('class', []))
		self.assertIn('badge-soft', competitor_badge.get('class', []))
		self.assertIn('badge-success', competitor_badge.get('class', []))
		active_cell = multi_role_cells[activation_column_index]
		self.assertIsNotNone(active_cell.select_one('.icon-\\[tabler--circle-check-filled\\].text-success'))

		admin_row = next(
			row for row in soup.select('tbody tr')
			if 'role-table-admin' in row.get_text(' ', strip=True)
		)
		admin_text = admin_row.get_text(' ', strip=True)
		self.assertNotIn('工作人员', admin_text)
		self.assertIn('超级用户', admin_text)
		admin_role_cell = admin_row.find_all('td')[roles_column_index]
		self.assertIsNone(admin_role_cell.find('span', string='工作人员'))
		admin_badge = admin_role_cell.find('span', string='超级用户')
		self.assertIn('badge-soft', admin_badge.get('class', []))
		self.assertIn('badge-error', admin_badge.get('class', []))

		inactive_user_row = next(
			row for row in soup.select('tbody tr')
			if '赵未分配' in row.get_text(' ', strip=True)
		)
		inactive_user_text = inactive_user_row.get_text(' ', strip=True)
		self.assertIn('未分配', inactive_user_text)
		inactive_user_cells = inactive_user_row.find_all('td')
		inactive_role_cell = inactive_user_cells[roles_column_index]
		self.assertIn('badge-soft', inactive_role_cell.find('span', string='未分配').get('class', []))
		inactive_cell = inactive_user_cells[activation_column_index]
		self.assertIsNotNone(inactive_cell.select_one('.icon-\\[tabler--circle-x-filled\\].text-error'))

	def test_user_list_orders_by_active_join_date_and_pk_by_default(self):
		response = self.client.get(reverse('accounts:user_list'))

		self.assertEqual(response.status_code, 200)
		soup = BeautifulSoup(response.content, 'html.parser')
		row_texts = [
			row.get_text(' ', strip=True)
			for row in soup.select('tbody tr')
		]
		multi_role_index = next(index for index, text in enumerate(row_texts) if '张多角' in text)
		coach_index = next(index for index, text in enumerate(row_texts) if '李教练' in text)
		admin_index = next(index for index, text in enumerate(row_texts) if 'role-table-admin' in text)
		inactive_index = next(index for index, text in enumerate(row_texts) if '赵未分配' in text)

		self.assertLess(multi_role_index, coach_index)
		self.assertLess(coach_index, admin_index)
		self.assertLess(admin_index, inactive_index)

	def test_join_date_sort_keeps_empty_join_dates_last(self):
		response = self.client.get(reverse('accounts:user_list'), {'sort': '-join_date'})

		self.assertEqual(response.status_code, 200)
		soup = BeautifulSoup(response.content, 'html.parser')
		row_texts = [
			row.get_text(' ', strip=True)
			for row in soup.select('tbody tr')
		]
		admin_index = next(index for index, text in enumerate(row_texts) if 'role-table-admin' in text)
		self.assertEqual(admin_index, len(row_texts) - 1)

	def test_role_sort_uses_stable_role_key_without_duplicate_rows(self):
		response = self.client.get(reverse('accounts:user_list'), {'sort': 'roles'})

		self.assertEqual(response.status_code, 200)
		soup = BeautifulSoup(response.content, 'html.parser')
		row_texts = [
			row.get_text(' ', strip=True)
			for row in soup.select('tbody tr')
		]
		self.assertEqual(
			sum('张多角' in text for text in row_texts),
			1,
		)

	def test_user_detail_uses_soft_role_badges(self):
		response = self.client.get(reverse('accounts:user_detail', args=[self.multi_role_user.pk]))

		self.assertEqual(response.status_code, 200)
		soup = BeautifulSoup(response.content, 'html.parser')
		coach_badge = soup.find('span', string='教练')
		competitor_badge = soup.find('span', string=GROUP_COMPETITOR)
		self.assertIn('badge-soft', coach_badge.get('class', []))
		self.assertIn('badge-primary', coach_badge.get('class', []))
		self.assertIn('badge-soft', competitor_badge.get('class', []))
		self.assertIn('badge-success', competitor_badge.get('class', []))

		response = self.client.get(reverse('accounts:user_detail', args=[self.admin.pk]))

		self.assertEqual(response.status_code, 200)
		soup = BeautifulSoup(response.content, 'html.parser')
		admin_badge = soup.find('span', string='超级用户')
		self.assertIsNotNone(admin_badge)
		self.assertIn('badge-soft', admin_badge.get('class', []))
		self.assertIn('badge-error', admin_badge.get('class', []))
		self.assertIsNone(soup.find('span', string='工作人员'))

	def test_deactivating_user_fills_empty_leave_date(self):
		user = User.objects.create_user('deactivate-user', password='testpass123')
		profile = UserProfile.objects.create(user=user)
		today = timezone.localdate()

		user.is_active = False
		user.save(update_fields=['is_active'])

		profile.refresh_from_db()
		self.assertEqual(profile.leave_date, today)

	def test_deactivating_user_preserves_existing_leave_date(self):
		user = User.objects.create_user('deactivate-existing-leave-date', password='testpass123')
		profile = UserProfile.objects.create(
			user=user,
			leave_date=date(2026, 5, 1),
		)

		user.is_active = False
		user.save(update_fields=['is_active'])

		profile.refresh_from_db()
		self.assertEqual(profile.leave_date, date(2026, 5, 1))

	def test_deactivating_user_without_profile_creates_leave_date(self):
		user = User.objects.create_user('deactivate-without-profile', password='testpass123')
		today = timezone.localdate()

		user.is_active = False
		user.save(update_fields=['is_active'])

		profile = UserProfile.objects.get(user=user)
		self.assertEqual(profile.leave_date, today)


class AccountPermissionBundleAccessTests(TestCase):
	def test_user_list_allows_access_via_view_all_profiles_bundle(self):
		user = User.objects.create_user('profile-viewer', password='testpass123')
		sync_user_permission_bundles(user, ['accounts.view_all_profiles'])
		self.client.force_login(user)

		response = self.client.get(reverse('accounts:user_list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '用户列表')

	def test_role_list_allows_access_via_view_all_profiles_bundle(self):
		user = User.objects.create_user('role-viewer', password='testpass123')
		sync_user_permission_bundles(user, ['accounts.view_all_profiles'])
		self.client.force_login(user)

		response = self.client.get(reverse('accounts:role_list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '角色列表')


class RoleListViewTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_superuser('role-list-admin', password='testpass123')
		self.role = Group.objects.create(name='教练')
		GroupProfile.objects.create(
			group=self.role,
			codename='coach',
			description='教练组',
			selected_permission_bundles=['training.maintain_training'],
		)
		for index in range(2):
			user = User.objects.create_user(
				username=f'coach-{index}',
				password='testpass123',
			)
			user.groups.add(self.role)
		self.client.force_login(self.admin)

	def test_role_list_shows_profile_user_count_and_permission_bundle_name(self):
		response = self.client.get(reverse('accounts:role_list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '教练')
		self.assertContains(response, 'coach')
		self.assertContains(response, '教练组')
		self.assertContains(response, '维护训练')

		soup = BeautifulSoup(response.content, 'html.parser')
		role_row = soup.find('td', string='教练').find_parent('tr')
		role_text = role_row.get_text(' ', strip=True)
		self.assertIn('2', role_text)


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
		extra_permission = Permission.objects.get(
			codename='add_group',
			content_type__app_label='auth',
			content_type__model='group',
		)

		sync_user_permission_bundles(user, ['training.maintain_training'], [extra_permission])

		user.refresh_from_db()
		self.assertEqual(user.profile.selected_permission_bundles, ['training.maintain_training'])
		self.assertSetEqual(
			set(user.user_permissions.values_list('codename', flat=True)),
			{
				'add_traininglog',
				'add_trainingcycle',
				'change_trainingcycle',
				'change_traininglog',
				'export_traininglog_archive',
				'view_all_traininglog',
				'view_trainingcycle',
				'view_traininglog',
				'add_group',
			},
		)

	def test_sync_group_permission_bundles_for_training_maintenance_grants_training_permissions(self):
		group = Group.objects.create(name='训练维护组')

		sync_group_permission_bundles(group, ['training.maintain_training'])

		group.refresh_from_db()
		self.assertEqual(group.profile.selected_permission_bundles, ['training.maintain_training'])
		self.assertSetEqual(
			set(group.permissions.values_list('codename', flat=True)),
			{
				'add_trainingcycle',
				'add_traininglog',
				'change_trainingcycle',
				'change_traininglog',
				'export_traininglog_archive',
				'view_all_traininglog',
				'view_trainingcycle',
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
		extra_permission = Permission.objects.get(
			codename='add_group',
			content_type__app_label='auth',
			content_type__model='group',
		)
		sync_user_permission_bundles(user, ['training.maintain_training'], [extra_permission])

		form = UserPermissionBundleAdminForm(instance=user)

		self.assertEqual(form.initial['selected_permission_bundles'], ['training.maintain_training'])
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
			Permission.objects.get(codename='add_trainingcycle'),
			Permission.objects.get(codename='add_traininglog'),
			Permission.objects.get(codename='change_trainingcycle'),
			Permission.objects.get(codename='change_traininglog'),
			Permission.objects.get(codename='export_traininglog_archive'),
			Permission.objects.get(codename='view_all_traininglog'),
			Permission.objects.get(codename='view_trainingcycle'),
			Permission.objects.get(codename='view_traininglog'),
		)

		output = StringIO()
		call_command('backfill_permission_bundles', stdout=output)

		self.assertFalse(hasattr(group, 'profile'))
		self.assertIn('用户组 预检查组: 业务权限包 -> training.maintain_training', output.getvalue())
		self.assertIn('以上为预检查结果', output.getvalue())

	def test_command_execute_backfills_group_and_user_bundles(self):
		group = Group.objects.create(name='训练日志组')
		group.permissions.add(
			Permission.objects.get(codename='add_trainingcycle'),
			Permission.objects.get(codename='add_traininglog'),
			Permission.objects.get(codename='change_trainingcycle'),
			Permission.objects.get(codename='change_traininglog'),
			Permission.objects.get(codename='export_traininglog_archive'),
			Permission.objects.get(codename='view_all_traininglog'),
			Permission.objects.get(codename='view_trainingcycle'),
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
		self.assertEqual(group.profile.selected_permission_bundles, ['training.maintain_training'])
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
