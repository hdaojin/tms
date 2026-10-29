from datetime import date, timedelta
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from accounts.services.profiles import update_profile


def lock_form_payload(response):
    """按 HTML form 归属收集锁定确认按钮实际提交的控件（含外部邮箱）。"""
    soup = BeautifulSoup(response.content, "html.parser")
    button = soup.select_one('#lock-profile-modal button[name="action"][value="lock"]')
    form = soup.find("form", id=button.get("form")) if button.get("form") else button.find_parent("form")
    payload = {}
    for control in soup.select("input[name], textarea[name], select[name]"):
        if control.has_attr("disabled"):
            continue
        owner = soup.find("form", id=control["form"]) if control.get("form") else control.find_parent("form")
        if owner is not form:
            continue
        if control.name == "select":
            option = control.select_one("option[selected]") or control.select_one("option")
            payload[control["name"]] = option.get("value", option.get_text()) if option else ""
        elif control.name == "textarea":
            # HTML 解析会忽略 textarea 起始标签后的第一个换行，BeautifulSoup 保留它。
            value = control.get_text()
            payload[control["name"]] = value[1:] if value.startswith("\n") else value
        else:
            payload[control["name"]] = control.get("value", "")
    payload[button["name"]] = button["value"]
    return payload


class PersonalProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profile-user",
            last_name="张",
            first_name="三",
            email="old@example.com",
        )
        self.profile = UserProfile.objects.create(user=self.user)
        self.client.force_login(self.user)
        self.url = reverse("accounts:profile")

    def test_full_name_and_editable_email(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'value="张三"')
        field = response.context["form"]["email"]
        self.assertEqual(field.value(), "old@example.com")
        self.assertFalse(field.field.disabled)
        self.assertContains(response, 'form="profile-form"')

    def test_save_and_lock_email(self):
        for action, email in [("save", "new@example.com"), ("lock", "locked@example.com")]:
            response = self.client.post(self.url, {"email": email, "action": action})
            self.assertRedirects(response, self.url)
            self.user.refresh_from_db()
            self.assertEqual(self.user.email, email)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.locked)
        response = self.client.get(self.url)
        self.assertTrue(response.context["form"].fields["email"].disabled)
        self.client.post(self.url, {"email": "tampered@example.com"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "locked@example.com")

    def test_lock_confirmation_submits_current_profile_and_external_email(self):
        self.profile.notes = "保留的备注"
        self.profile.phone_number = "13800138000"
        self.profile.save()
        response = self.client.get(self.url)
        payload = lock_form_payload(response)
        self.assertEqual(payload["notes"], "保留的备注")
        self.assertEqual(payload["phone_number"], "13800138000")
        self.assertEqual(payload["email"], "old@example.com")
        payload["notes"] = "确认前新填写的备注"
        self.assertRedirects(self.client.post(self.url, payload), self.url)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.profile.notes, "确认前新填写的备注")
        self.assertEqual(self.profile.phone_number, "13800138000")
        self.assertEqual(self.user.email, "old@example.com")
        self.assertTrue(self.profile.locked)

    def test_invalid_email_does_not_save_or_lock(self):
        response = self.client.post(self.url, {"email": "invalid", "action": "lock"})
        self.assertFormError(response.context["form"], "email", "输入一个有效的 Email 地址。")
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.email, "old@example.com")
        self.assertFalse(self.profile.locked)

    def test_email_can_be_cleared(self):
        self.client.post(self.url, {"email": ""})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "")

    def test_user_detail_title_uses_full_name(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        response = self.client.get(reverse("accounts:user_detail", args=[self.user.pk]))
        self.assertEqual(response.context["title"], "张三的详细信息")
        self.assertContains(response, "张三的详细信息")

    def test_signup_confirmation_uses_full_name(self):
        html = render_to_string("accounts/signup_done.html", {"new_user": self.user})
        self.assertIn("(张三)", html)

    def test_notice_publisher_uses_full_name(self):
        from notices.models import Notice

        notice = Notice.objects.create(title="姓名显示测试", content="通知正文", published_by=self.user)
        for template in ["notices/notice_detail.html", "notices/notice_list_partial.html"]:
            with self.subTest(template=template):
                html = render_to_string(template, {"notice": notice, "notices": [notice]})
                self.assertIn("张三", html)
                self.assertNotIn("三 张", html)


class AdminProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("profile-admin", "admin@example.com", None)
        cls.target = User.objects.create_user(
            "target-profile", last_name="李", first_name="四", email="target@example.com"
        )
        cls.profile = UserProfile.objects.create(
            user=cls.target,
            notes="原资料",
            student_id="PROFILE-001",
            join_date=date(2026, 1, 1),
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("accounts:user_detail", args=[self.target.pk])

    def test_admin_can_edit_and_locked_state_requires_unlock(self):
        response = self.client.get(self.url)
        self.assertTrue(response.context["can_edit_profile"])
        self.assertTrue(all(not field.disabled for field in response.context["form"].fields.values()))
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual(len(soup.select('input[name="email"]')), 1)
        self.assertEqual(soup.select_one('input[name="email"]')["form"], "profile-form")
        self.assertIsNotNone(soup.select_one('#profile-form button[value="save"]'))
        self.assertIsNotNone(soup.select_one('#lock-profile-modal button[form="profile-form"]'))
        self.profile.locked = True
        self.profile.save()
        response = self.client.get(self.url)
        self.assertFalse(response.context["can_edit_profile"])
        self.assertTrue(all(field.disabled for field in response.context["form"].fields.values()))
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertTrue(soup.select_one('#profile-form button[value="save"]').has_attr("disabled"))
        self.assertIsNotNone(soup.select_one('#unlock-profile-modal button[value="unlock"]'))

    def test_save_edits_target_preserving_account_identity_flags_and_actor(self):
        response = self.client.post(
            self.url,
            {
                "action": "save",
                "email": "new-target@example.com",
                "notes": "管理员填写",
                "student_id": "PROFILE-002",
                "username": "hijacked",
                "first_name": "改名",
                "user": self.admin.pk,
                "is_superuser": "on",
                "is_active": "",
                "locked": "on",
            },
        )
        self.assertRedirects(response, self.url)
        self.target.refresh_from_db()
        self.admin.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.target.email, "new-target@example.com")
        self.assertEqual(self.admin.email, "admin@example.com")
        self.assertEqual(self.profile.notes, "管理员填写")
        self.assertEqual(self.profile.student_id, "PROFILE-002")
        self.assertFalse(self.profile.locked)
        self.assertEqual(self.target.username, "target-profile")
        self.assertEqual(self.target.first_name, "四")
        self.assertFalse(self.target.is_superuser)
        self.assertTrue(self.target.is_active)

    def test_save_and_lock_from_rendered_confirmation_preserves_full_data(self):
        payload = lock_form_payload(self.client.get(self.url))
        payload["notes"] = "保存并锁定的备注"
        payload["email"] = "locked-target@example.com"
        self.assertRedirects(self.client.post(self.url, payload), self.url)
        self.profile.refresh_from_db()
        self.target.refresh_from_db()
        self.assertTrue(self.profile.locked)
        self.assertEqual(self.profile.notes, "保存并锁定的备注")
        self.assertEqual(self.profile.student_id, "PROFILE-001")
        self.assertEqual(self.target.email, "locked-target@example.com")

    def test_invalid_data_keeps_inputs_and_neither_saves_nor_locks(self):
        for values in (
            {"email": "invalid"},
            {"birth_date": (timezone.localdate() + timedelta(days=1)).isoformat()},
            {"join_date": "2026-03-01", "leave_date": "2026-02-01"},
        ):
            with self.subTest(values=values):
                response = self.client.post(
                    self.url,
                    {
                        "action": "lock",
                        "email": "valid@example.com",
                        "notes": "保留输入",
                        **values,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(response.context["form"]["notes"].value(), "保留输入")
                self.profile.refresh_from_db()
                self.target.refresh_from_db()
                self.assertFalse(self.profile.locked)
                self.assertEqual(self.profile.notes, "原资料")
                self.assertEqual(self.target.email, "target@example.com")

    def test_duplicate_student_id_is_rejected(self):
        UserProfile.objects.create(user=self.admin, student_id="ADMIN-ID")
        response = self.client.post(self.url, {"student_id": "ADMIN-ID", "email": "target@example.com"})
        self.assertTrue(response.context["form"].errors["student_id"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.student_id, "PROFILE-001")

    def test_locked_save_or_lock_cannot_bypass_lock(self):
        self.profile.locked = True
        self.profile.save()
        for action in ("save", "lock"):
            response = self.client.post(
                self.url, {"action": action, "notes": "伪造保存", "email": "forged@example.com", "locked": ""}
            )
            self.assertRedirects(response, self.url)
        self.profile.refresh_from_db()
        self.target.refresh_from_db()
        self.assertTrue(self.profile.locked)
        self.assertEqual(self.profile.notes, "原资料")
        self.assertEqual(self.target.email, "target@example.com")

    def test_unlock_ignores_other_fields_and_owner_can_edit_again(self):
        self.profile.locked = True
        self.profile.save()
        response = self.client.post(
            self.url, {"action": "unlock", "notes": "不能保存", "email": "invalid", "birth_date": "invalid"}
        )
        self.assertRedirects(response, self.url)
        self.profile.refresh_from_db()
        self.target.refresh_from_db()
        self.assertFalse(self.profile.locked)
        self.assertEqual(self.profile.notes, "原资料")
        self.assertEqual(self.target.email, "target@example.com")
        self.client.force_login(self.target)
        response = self.client.post(
            reverse("accounts:profile"), {"notes": "本人重新编辑", "email": "owner@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.notes, "本人重新编辑")

    def test_viewers_and_staff_remain_readonly_even_with_model_change_permissions(self):
        for staff in (False, True):
            viewer = User.objects.create_user(f"profile-viewer-{staff}", is_staff=staff)
            viewer.user_permissions.set(
                Permission.objects.filter(
                    codename__in=["view_all_profiles", "change_userprofile", "change_user"],
                    content_type__app_label__in=["accounts", "auth"],
                )
            )
            self.client.force_login(viewer)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(all(field.disabled for field in response.context["form"].fields.values()))
            self.assertFalse(response.context["can_manage_profile"])
            self.assertNotContains(response, 'id="profile-form"')
            self.assertNotContains(response, 'id="lock-profile-modal"')
            self.assertNotContains(response, 'id="unlock-profile-modal"')
            for action in ("save", "lock", "unlock"):
                self.assertEqual(self.client.post(self.url, {"action": action, "notes": "伪造"}).status_code, 403)

    def test_service_rechecks_admin_authority_and_owner_cannot_unlock(self):
        User.objects.filter(pk=self.admin.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            update_profile(actor=self.admin, target_id=self.target.pk, action="save", data={})
        User.objects.filter(pk=self.admin.pk).update(is_superuser=True, is_active=False)
        with self.assertRaises(PermissionDenied):
            update_profile(actor=self.admin, target_id=self.target.pk, action="unlock", data={})
        with self.assertRaises(PermissionDenied):
            update_profile(actor=self.target, target_id=self.target.pk, action="unlock", data={})
        self.client.force_login(self.target)
        self.assertEqual(self.client.post(reverse("accounts:profile"), {"action": "unlock"}).status_code, 403)

    def test_email_and_profile_write_rollback_together(self):
        with (
            patch.object(UserProfile, "save", side_effect=RuntimeError("write failed")),
            self.assertRaises(RuntimeError),
        ):
            update_profile(
                actor=self.admin,
                target_id=self.target.pk,
                action="lock",
                data={"email": "rollback@example.com", "notes": "不能保存"},
            )
        self.target.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.target.email, "target@example.com")
        self.assertEqual(self.profile.notes, "原资料")
        self.assertFalse(self.profile.locked)

    def test_csrf_and_unknown_action(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url, {"action": "unlock"}).status_code, 403)
        self.assertRedirects(self.client.post(self.url, {"action": "invalid"}), self.url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.notes, "原资料")
