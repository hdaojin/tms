from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from accounts.services.permission_assignments import sync_group_permission_assignments
from accounts.services.roles import preview_user_roles, save_user_roles

User = get_user_model()


class BasicAccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("unassigned-profile")
        self.other = User.objects.create_user("other-profile")
        self.client.force_login(self.user)

    def test_zero_permissions_can_see_panel_and_maintain_only_own_profile(self):
        self.assertFalse(self.user.get_all_permissions())
        panel = self.client.get(reverse("accounts:home"))
        self.assertContains(panel, "功能面板")
        self.assertContains(panel, reverse("accounts:profile"))
        self.assertContains(panel, "用户中心")
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
        other = UserProfile.objects.create(user=self.other, notes="他人资料")
        result = self.client.post(
            reverse("accounts:profile"),
            {"notes": "本人资料", "user": self.other.pk, "is_superuser": "on", "action": "save"},
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(UserProfile.objects.get(user=self.user).notes, "本人资料")
        other.refresh_from_db()
        self.assertEqual(other.notes, "他人资料")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.groups.exists())
        self.assertFalse(self.user.user_permissions.exists())

    def test_locked_profile_remains_readonly_and_cannot_be_unlocked_by_post(self):
        profile = UserProfile.objects.create(user=self.user, locked=True, notes="锁定内容")
        self.assertContains(self.client.get(reverse("accounts:profile")), "资料已锁定")
        self.client.post(reverse("accounts:profile"), {"notes": "绕过", "locked": "", "action": "save"})
        profile.refresh_from_db()
        self.assertTrue(profile.locked)
        self.assertEqual(profile.notes, "锁定内容")


class UserRoleAssignmentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("assignment-admin", "admin@example.invalid", None)
        self.user = User.objects.create_user("assignment-target")
        self.group = Group.objects.create(name="训练角色")
        sync_group_permission_assignments(self.group, ["training.maintain_own_logs"])
        self.url = reverse("accounts:user_roles", args=[self.user.pk])

    def test_preview_save_entrypoints_and_direct_permissions_are_preserved(self):
        direct = Permission.objects.get(content_type__app_label="notes", codename="view_noterepo")
        self.user.user_permissions.add(direct)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("accounts:user_list")), self.url)
        self.assertContains(self.client.get(reverse("accounts:user_detail", args=[self.user.pk])), self.url)
        preview = self.client.post(self.url, {"roles": [self.group.pk], "action": "preview"})
        self.assertContains(preview, "训练角色")
        self.assertContains(preview, "保存前变更摘要")
        self.assertFalse(self.user.groups.exists())
        saved = self.client.post(
            self.url, {"roles": [self.group.pk], "action": "save", "preview_token": preview.context["preview"]["token"]}
        )
        self.assertEqual(saved.status_code, 302)
        self.assertTrue(self.user.groups.filter(pk=self.group.pk).exists())
        self.assertTrue(self.user.user_permissions.filter(pk=direct.pk).exists())
        preview = preview_user_roles(actor=self.admin, user=self.user, role_ids=[])
        save_user_roles(actor=self.admin, user=self.user, role_ids=[], token=preview["token"])
        self.assertFalse(self.user.groups.exists())
        self.assertTrue(self.user.user_permissions.filter(pk=direct.pk).exists())

    def test_ordinary_staff_cannot_assign_roles_even_with_user_view_permission(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.add(
            Permission.objects.get(content_type__app_label="accounts", codename="view_all_profiles")
        )
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse("accounts:user_list")), "分配角色")
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {"roles": [self.group.pk], "action": "save"}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            preview_user_roles(actor=self.user, user=self.admin, role_ids=[self.group.pk])

    def test_changed_roles_or_changed_form_invalidate_preview(self):
        preview = preview_user_roles(actor=self.admin, user=self.user, role_ids=[self.group.pk])
        with self.assertRaises(ValidationError):
            save_user_roles(actor=self.admin, user=self.user, role_ids=[], token=preview["token"])
        sync_group_permission_assignments(self.group, ["notes.view_notes"])
        with self.assertRaises(ValidationError):
            save_user_roles(actor=self.admin, user=self.user, role_ids=[self.group.pk], token=preview["token"])
        self.assertFalse(self.user.groups.exists())
        fresh = preview_user_roles(actor=self.admin, user=self.user, role_ids=[self.group.pk])
        self.user.groups.add(self.group)
        with self.assertRaises(ValidationError):
            save_user_roles(actor=self.admin, user=self.user, role_ids=[self.group.pk], token=fresh["token"])
        with self.assertRaises(ValidationError):
            save_user_roles(actor=self.admin, user=self.user, role_ids=[], token="forged")
