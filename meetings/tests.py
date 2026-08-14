from datetime import date
from io import StringIO

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .models import Meeting, meeting_file_upload_to


class MeetingUrlTests(TestCase):
	def test_meeting_list_is_mounted_at_app_root(self):
		self.assertEqual(reverse('meetings:meeting_list'), '/meetings/')

	def test_meeting_file_upload_path_uses_meetings_directory(self):
		meeting = Meeting(title='班会', date=date(2026, 1, 2))
		self.assertEqual(
			meeting_file_upload_to(meeting, 'minutes.pdf'),
			'2026/2026.01.02-班会.pdf',
		)

	def test_cutover_command_is_noop_on_fresh_meetings_schema(self):
		stdout = StringIO()

		call_command('cutover_meeting_to_meetings', stdout=stdout)

		self.assertIn('当前数据库与文件目录已经使用 meetings，无需切换。', stdout.getvalue())



class MeetingCutoverCommandTests(TransactionTestCase):
	def test_cutover_command_recovers_dual_table_state_when_new_table_is_empty(self):
		meeting = Meeting.objects.create(title='周会', date=date(2026, 1, 3), file='meetings/2026/2026.01.03-weekly.pdf')
		MigrationRecorder.Migration.objects.create(app='meeting', name='0001_initial')
		old_content_type = ContentType.objects.create(app_label='meeting', model='meeting')
		Permission.objects.create(
			name='旧会议查看权限',
			codename='view_meeting_legacy',
			content_type=old_content_type,
		)

		self.addCleanup(
			lambda: connection.cursor().execute('DROP TABLE IF EXISTS meeting_meeting')
		)
		self.addCleanup(
			lambda: connection.cursor().execute('DROP TABLE IF EXISTS meetings_meeting_empty_backup')
		)
		with connection.cursor() as cursor:
			cursor.execute('CREATE TABLE meeting_meeting AS SELECT * FROM meetings_meeting')
			cursor.execute('DELETE FROM meetings_meeting')

		stdout = StringIO()
		call_command('cutover_meeting_to_meetings', '--execute', stdout=stdout)

		self.assertIn('meeting 已切换为 meetings', stdout.getvalue())
		self.assertEqual(Meeting.objects.count(), 1)
		self.assertEqual(Meeting.objects.get().pk, meeting.pk)
		self.assertFalse(MigrationRecorder.Migration.objects.filter(app='meeting').exists())
		self.assertFalse(ContentType.objects.filter(app_label='meeting', model='meeting').exists())
		self.assertTrue(
			Permission.objects.filter(codename='view_meeting_legacy', content_type__app_label='meetings').exists()
		)
