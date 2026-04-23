from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Meeting, meeting_file_upload_to


class MeetingUrlTests(TestCase):
	def test_meeting_list_is_mounted_at_app_root(self):
		self.assertEqual(reverse('meetings:meeting_list'), '/meetings/')

	def test_meeting_file_upload_path_uses_meetings_directory(self):
		meeting = Meeting(title='班会', date=date(2026, 1, 2))
		self.assertEqual(
			meeting_file_upload_to(meeting, 'minutes.pdf'),
			'meetings/2026/2026.01.02-班会.pdf',
		)

	def test_cutover_command_is_noop_on_fresh_meetings_schema(self):
		stdout = StringIO()

		call_command('cutover_meeting_to_meetings', stdout=stdout)

		self.assertIn('当前数据库与文件目录已经使用 meetings，无需切换。', stdout.getvalue())
