from django.contrib.auth.models import Group
from django.test import TestCase

from accounts.services.permission_assignments import sync_group_permission_assignments
from core.permissions import get_permission_bundle_choices


class ForumPermissionBundleTests(TestCase):
    def test_translate_forum_bundle_is_available_and_grants_publish_permissions(self):
        bundle_code = "worldskills_forum.translate_forum"
        self.assertIn((bundle_code, "世赛论坛 | 翻译世赛论坛"), get_permission_bundle_choices())
        group = Group.objects.create(name="论坛翻译人员")

        sync_group_permission_assignments(group, [bundle_code])

        group.refresh_from_db()
        self.assertEqual(group.profile.selected_permission_bundles, [bundle_code])
        self.assertSetEqual(
            set(
                group.permissions.values_list(
                    "content_type__app_label",
                    "codename",
                )
            ),
            {
                ("worldskills_forum", "view_forumtopic"),
                ("worldskills_forum", "add_forumtopic"),
                ("worldskills_forum", "change_forumtopic"),
                ("worldskills_forum", "view_forumpost"),
                ("worldskills_forum", "add_forumpost"),
                ("worldskills_forum", "change_forumpost"),
                ("worldskills_forum", "view_forumtranslation"),
                ("worldskills_forum", "add_forumtranslation"),
                ("worldskills_forum", "change_forumtranslation"),
                ("worldskills_forum", "view_forumpostattachment"),
                ("worldskills_forum", "add_forumpostattachment"),
                ("worldskills_forum", "change_forumpostattachment"),
            },
        )
