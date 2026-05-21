from io import StringIO

from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase

from accounts.services.permission_bundles import sync_group_permission_bundles


class MeetingPermissionBundleTests(TestCase):
    def test_sync_group_permission_bundles_for_meeting_upload_grants_add_permission(self):
        group = Group.objects.create(name="会议上传组")

        sync_group_permission_bundles(group, ["meetings.upload_meeting"])

        group.refresh_from_db()
        self.assertEqual(group.profile.selected_permission_bundles, ["meetings.upload_meeting"])
        self.assertSetEqual(
            set(group.permissions.values_list("codename", flat=True)),
            {"add_meeting"},
        )

    def test_backfill_command_infers_meeting_upload_bundle(self):
        group = Group.objects.create(name="班务")
        group.permissions.add(
            Permission.objects.get(codename="add_meeting"),
            Permission.objects.get(codename="add_notice"),
        )

        output = StringIO()
        call_command("backfill_permission_bundles", "--groups-only", stdout=output)

        text = output.getvalue()
        self.assertIn("用户组 班务: 业务权限包 -> meetings.upload_meeting", text)
        self.assertIn("额外原生权限 -> notices.add_notice", text)