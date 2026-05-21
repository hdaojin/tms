from io import StringIO

from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase

from accounts.services.permission_bundles import sync_group_permission_bundles


class PermissionBundleCoverageTests(TestCase):
    def test_sync_group_permission_bundles_for_single_permission_business_actions(self):
        bundle_cases = {
            "accounts.view_all_profiles": "view_all_profiles",
            "assessments.view_all_scores": "view_all_scores",
            "competitions.create_competitor": "add_competitor",
            "competitions.create_expert": "add_expert",
            "competitions.create_skillposition": "add_skillposition",
            "competitions.link_member": "add_member",
            "competitions.record_competition_result": "add_competitionresult",
            "meetings.delete_meeting": "delete_meeting",
            "meetings.upload_meeting": "add_meeting",
            "notices.publish_notice": "add_notice",
        }

        for bundle_code, codename in bundle_cases.items():
            with self.subTest(bundle_code=bundle_code):
                group = Group.objects.create(name=f"group-{bundle_code}")

                sync_group_permission_bundles(group, [bundle_code])

                group.refresh_from_db()
                self.assertEqual(group.profile.selected_permission_bundles, [bundle_code])
                self.assertSetEqual(
                    set(group.permissions.values_list("codename", flat=True)),
                    {codename},
                )

    def test_backfill_command_overwrite_merges_existing_and_new_bundles(self):
        group = Group.objects.create(name="班务")
        sync_group_permission_bundles(group, ["meetings.upload_meeting"])
        group.permissions.add(Permission.objects.get(codename="add_notice"))

        output = StringIO()
        call_command(
            "backfill_permission_bundles",
            "--groups-only",
            "--overwrite",
            "--execute",
            stdout=output,
        )

        group.refresh_from_db()
        self.assertEqual(
            group.profile.selected_permission_bundles,
            ["meetings.upload_meeting", "notices.publish_notice"],
        )
        self.assertSetEqual(
            set(group.permissions.values_list("codename", flat=True)),
            {"add_meeting", "add_notice"},
        )
        self.assertIn("已回填", output.getvalue())

    def test_backfill_command_keeps_unbundled_permissions_as_extra(self):
        group = Group.objects.create(name="会议管理员")
        group.permissions.add(
            Permission.objects.get(codename="add_meeting"),
            Permission.objects.get(codename="view_meeting"),
        )

        output = StringIO()
        call_command("backfill_permission_bundles", "--groups-only", stdout=output)

        text = output.getvalue()
        self.assertIn("用户组 会议管理员: 业务权限包 -> meetings.upload_meeting", text)
        self.assertIn("额外原生权限 -> meetings.view_meeting", text)