from pathlib import Path
import shutil

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.services.permission_bundles import sync_user_permission_bundles

from .models import Notice, NoticeAttachment


User = get_user_model()


class NoticeAttachmentCleanupTests(TestCase):
	def setUp(self):
		self.temp_media = Path.cwd() / ".tmp-test-notices-media"
		shutil.rmtree(self.temp_media, ignore_errors=True)
		self.override = override_settings(MEDIA_ROOT=self.temp_media)
		self.override.enable()
		self.notice = Notice.objects.create(title='测试通知', content='测试内容')

	def tearDown(self):
		for attachment in NoticeAttachment.objects.all():
			if attachment.file:
				attachment.file.delete(save=False)

		self.override.disable()
		shutil.rmtree(self.temp_media, ignore_errors=True)
		super().tearDown()

	def _build_upload_file(self, name='notice-attachment.txt'):
		return SimpleUploadedFile(name, b'notice attachment content', content_type='text/plain')

	def test_deleting_notice_attachment_removes_physical_file(self):
		attachment = NoticeAttachment.objects.create(
			notice=self.notice,
			file=self._build_upload_file('delete-attachment.txt'),
		)
		file_path = Path(attachment.file.path)

		self.assertTrue(file_path.exists())

		attachment.delete()

		self.assertFalse(file_path.exists())

	def test_deleting_notice_removes_all_attachment_files(self):
		first_attachment = NoticeAttachment.objects.create(
			notice=self.notice,
			file=self._build_upload_file('notice-delete-1.txt'),
		)
		second_attachment = NoticeAttachment.objects.create(
			notice=self.notice,
			file=self._build_upload_file('notice-delete-2.txt'),
		)
		file_paths = [Path(first_attachment.file.path), Path(second_attachment.file.path)]

		self.notice.delete()

		self.assertFalse(NoticeAttachment.objects.exists())
		for file_path in file_paths:
			self.assertFalse(file_path.exists())

	def test_replacing_notice_attachment_removes_old_file(self):
		attachment = NoticeAttachment.objects.create(
			notice=self.notice,
			file=self._build_upload_file('notice-old.txt'),
		)
		old_path = Path(attachment.file.path)

		attachment.file = self._build_upload_file('notice-new.txt')
		attachment.save()
		new_path = Path(attachment.file.path)

		self.assertFalse(old_path.exists())
		self.assertTrue(new_path.exists())


class NoticeUrlTests(TestCase):
	def test_notice_list_is_mounted_at_app_root(self):
		self.assertEqual(reverse('notices:notice_list'), '/notices/')


class NoticeAttachmentUploadTests(TestCase):
	def setUp(self):
		self.temp_media = Path.cwd() / ".tmp-test-notices-media"
		shutil.rmtree(self.temp_media, ignore_errors=True)
		self.override = override_settings(MEDIA_ROOT=self.temp_media)
		self.override.enable()
		self.user = User.objects.create_user(
			username='notice-viewer',
			password='testpass123',
		)
		self.publisher = User.objects.create_user(
			username='notice-publisher',
			password='testpass123',
		)
		sync_user_permission_bundles(self.publisher, ['notices.publish_notice'])

	def tearDown(self):
		for attachment in NoticeAttachment.objects.all():
			if attachment.file:
				attachment.file.delete(save=False)

		self.override.disable()
		shutil.rmtree(self.temp_media, ignore_errors=True)
		super().tearDown()

	def _build_upload_file(self, name):
		return SimpleUploadedFile(name, b'notice attachment content', content_type='text/plain')

	def test_notice_create_requires_add_permission(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('notices:notice_create'))

		self.assertEqual(response.status_code, 403)

	def test_notice_create_accepts_multiple_attachments(self):
		self.client.force_login(self.publisher)

		response = self.client.post(
			reverse('notices:notice_create'),
			{
				'title': '多附件通知',
				'content': '通知内容',
				'send_to_all': 'on',
				'attachments': [
					self._build_upload_file('notice-1.txt'),
					self._build_upload_file('notice-2.txt'),
				],
			},
		)

		self.assertEqual(response.status_code, 302)
		notice = Notice.objects.get(title='多附件通知')
		self.assertEqual(notice.published_by, self.publisher)
		self.assertEqual(notice.attachments.count(), 2)
		self.assertCountEqual(
			[attachment.file_name for attachment in notice.attachments.all()],
			['notice-1.txt', 'notice-2.txt'],
		)
