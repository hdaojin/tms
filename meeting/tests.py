from django.test import TestCase
from django.urls import reverse


class MeetingUrlTests(TestCase):
	def test_meeting_list_is_mounted_at_app_root(self):
		self.assertEqual(reverse('meeting:meeting_list'), '/meeting/')
