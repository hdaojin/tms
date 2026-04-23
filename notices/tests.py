from pathlib import Path
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Notice, NoticeAttachment


class NoticeAttachmentCleanupTests(TestCase):
	def setUp(self):
		self.temp_media = tempfile.TemporaryDirectory()
		self.override = override_settings(MEDIA_ROOT=self.temp_media.name)
		self.override.enable()
		self.notice = Notice.objects.create(title='测试通知', content='测试内容')

	def tearDown(self):
		for attachment in NoticeAttachment.objects.all():
			if attachment.file:
				attachment.file.delete(save=False)

		self.override.disable()
		self.temp_media.cleanup()
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
