from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import SambaOperation
from .services import mark_stale_running_operations, process_operation


@override_settings(SAMBA_INTEGRATION_ENABLED=True, SAMBA_ASYNC_OPERATIONS_ENABLED=False)
class SambaAccountViewTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='samba-user', password='testpass123')
		self.user.user_permissions.add(
			Permission.objects.get(
				content_type__app_label='samba', codename='add_sambaoperation'
			)
		)
		self.client.force_login(self.user)

	@patch('samba.services.enable_samba_for_user', return_value={'username': 'samba-user', 'created': True})
	def test_enable_post_creates_audit_operation(self, mocked_enable):
		response = self.client.post(
			reverse('samba:accounts'),
			{
				'action': 'enable',
				'password1': 'ValidPass123',
				'password2': 'ValidPass123',
			},
			follow=True,
		)

		self.assertRedirects(response, reverse('samba:accounts'))
		operation = SambaOperation.objects.get(target_user=self.user)
		self.assertEqual(operation.action, SambaOperation.Action.ENABLE)
		self.assertEqual(operation.status, SambaOperation.Status.SUCCEEDED)
		self.assertEqual(operation.created_by, self.user)
		self.assertEqual(operation.result_summary, 'Samba 账户已开通。')
		mocked_enable.assert_called_once()

	@override_settings(SAMBA_ASYNC_OPERATIONS_ENABLED=True)
	@patch('samba.services.enable_samba_for_user', return_value={'username': 'samba-user', 'created': True})
	def test_enable_post_only_queues_operation_in_async_mode(self, mocked_enable):
		response = self.client.post(
			reverse('samba:accounts'),
			{
				'action': 'enable',
				'password1': 'ValidPass123',
				'password2': 'ValidPass123',
			},
			follow=True,
		)

		self.assertRedirects(response, reverse('samba:accounts'))
		operation = SambaOperation.objects.get(target_user=self.user)
		self.assertEqual(operation.action, SambaOperation.Action.ENABLE)
		self.assertEqual(operation.status, SambaOperation.Status.QUEUED)
		self.assertEqual(operation.result_summary, '已提交，等待处理。')
		mocked_enable.assert_not_called()

	@override_settings(SAMBA_INTEGRATION_ENABLED=False)
	def test_submit_operation_honors_feature_flag(self):
		response = self.client.post(
			reverse('samba:accounts'),
			{
				'action': 'enable',
				'password1': 'ValidPass123',
				'password2': 'ValidPass123',
			},
			follow=True,
		)

		self.assertContains(response, 'Samba 集成功能当前已关闭，请联系管理员。')
		self.assertFalse(SambaOperation.objects.exists())

	def test_get_uses_last_known_state_without_runtime_probe(self):
		SambaOperation.objects.create(
			target_user=self.user,
			action=SambaOperation.Action.ENABLE,
			status=SambaOperation.Status.SUCCEEDED,
			result_summary='Samba 账户已开通。',
			created_by=self.user,
		)

		with patch('samba.views.get_last_known_enabled_state', return_value=True) as mocked_state:
			response = self.client.get(reverse('samba:accounts'))

		self.assertEqual(response.status_code, 200)
		mocked_state.assert_called()
		self.assertContains(response, '最近一次已知状态为已开通')


class SambaOperationProcessingTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='processor-user', password='testpass123')

	@patch('samba.services.enable_samba_for_user', return_value={'username': 'processor-user', 'created': False})
	def test_process_operation_marks_success_and_clears_payload(self, mocked_enable):
		operation = SambaOperation.objects.create(
			target_user=self.user,
			action=SambaOperation.Action.ENABLE,
			status=SambaOperation.Status.QUEUED,
			payload_encrypted='gAAAAABpA',
			created_by=self.user,
		)

		with patch('samba.services._decrypt_payload', return_value={'password': 'ValidPass123'}):
			process_operation(operation.pk)

		operation.refresh_from_db()
		self.assertEqual(operation.status, SambaOperation.Status.SUCCEEDED)
		self.assertEqual(operation.result_summary, 'Samba 账户已更新密码与组。')
		self.assertEqual(operation.payload_encrypted, '')
		mocked_enable.assert_called_once_with(self.user, 'ValidPass123')

	def test_process_operation_marks_failure(self):
		operation = SambaOperation.objects.create(
			target_user=self.user,
			action=SambaOperation.Action.ENABLE,
			status=SambaOperation.Status.QUEUED,
			payload_encrypted='gAAAAABpA',
			created_by=self.user,
		)

		with patch('samba.services._decrypt_payload', return_value={'password': 'ValidPass123'}), patch(
			'samba.services.enable_samba_for_user',
			side_effect=RuntimeError('groupadd failed'),
		):
			process_operation(operation.pk)

		operation.refresh_from_db()
		self.assertEqual(operation.status, SambaOperation.Status.FAILED)
		self.assertEqual(operation.result_summary, '执行失败。')
		self.assertIn('groupadd failed', operation.last_error)

	@override_settings(SAMBA_OPERATION_STALE_MINUTES=30)
	def test_mark_stale_running_operations_marks_failure_and_clears_payload(self):
		now = timezone.now()
		stale_operation = SambaOperation.objects.create(
			target_user=self.user,
			action=SambaOperation.Action.ENABLE,
			status=SambaOperation.Status.RUNNING,
			payload_encrypted='encrypted-payload',
			result_summary='后台处理中。',
			started_at=now - timedelta(minutes=31),
			created_by=self.user,
		)
		fresh_operation = SambaOperation.objects.create(
			target_user=self.user,
			action=SambaOperation.Action.CHANGE_PASSWORD,
			status=SambaOperation.Status.RUNNING,
			payload_encrypted='fresh-payload',
			result_summary='后台处理中。',
			started_at=now - timedelta(minutes=5),
			created_by=self.user,
		)

		count = mark_stale_running_operations(now=now)

		self.assertEqual(count, 1)
		stale_operation.refresh_from_db()
		fresh_operation.refresh_from_db()
		self.assertEqual(stale_operation.status, SambaOperation.Status.FAILED)
		self.assertEqual(stale_operation.payload_encrypted, '')
		self.assertIn('超时', stale_operation.last_error)
		self.assertEqual(fresh_operation.status, SambaOperation.Status.RUNNING)
		self.assertEqual(fresh_operation.payload_encrypted, 'fresh-payload')
