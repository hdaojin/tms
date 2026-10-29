from datetime import date
from time import time
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib.auth.models import Group, Permission, User
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import UserProfile
from accounts.services.user_management import SALT, preview_users, save_users


class UserManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("manager", "manager@example.com", "password")
        cls.user = User.objects.create_user("student", last_name="张", first_name="三")
        cls.other = User.objects.create_user("other", is_active=False)
        cls.role = Group.objects.create(name="选手")
        cls.existing = Group.objects.create(name="现有角色")
        cls.permission = Permission.objects.get(codename="view_user", content_type__app_label="auth")

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("accounts:user_manage")

    def payload(self, operation="deactivate", roles=None, leave_date=None):
        return {"operation": operation, "roles": roles or [], "leave_date": leave_date}

    def preview(self, operation="deactivate", ids=None, **kwargs):
        return preview_users(actor=self.admin, ids=ids or [self.user.pk], payload=self.payload(operation, **kwargs))

    def save(self, preview):
        return save_users(actor=self.admin, token=preview["token"])

    def test_activation_is_independent_of_dates_and_does_not_create_profile(self):
        self.save(self.preview())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        profile = UserProfile.objects.create(user=self.user, leave_date=date(2026, 1, 1))
        self.save(self.preview("activate"))
        profile.refresh_from_db()
        self.assertEqual(profile.leave_date, date(2026, 1, 1))
        result = self.save(self.preview("activate"))
        self.assertEqual(result["changed"], 0)

    def test_add_and_remove_roles_preserve_other_roles_and_direct_permissions(self):
        self.user.groups.add(self.existing)
        self.user.user_permissions.add(self.permission)
        self.save(self.preview("add_roles", roles=[self.role.pk]))
        self.assertSetEqual(set(self.user.groups.all()), {self.existing, self.role})
        self.save(self.preview("remove_roles", roles=[self.role.pk]))
        self.assertSetEqual(set(self.user.groups.all()), {self.existing})
        self.assertTrue(self.user.user_permissions.filter(pk=self.permission.pk).exists())
        self.assertEqual(self.preview("remove_roles", roles=[self.role.pk])["unchanged"], 1)

    def test_role_preview_reports_permission_changes_with_direct_grants_preserved(self):
        self.role.permissions.add(self.permission)
        preview = self.preview("add_roles", roles=[self.role.pk])
        self.assertEqual(len(preview["rows"][0]["granted"]), 1)
        self.user.groups.add(self.role)
        self.user.user_permissions.add(self.permission)
        preview = self.preview("remove_roles", roles=[self.role.pk])
        self.assertEqual(preview["rows"][0]["revoked"], [])

    def test_superuser_protection_rejects_entire_batch(self):
        for operation in ("deactivate", "add_roles", "remove_roles"):
            with self.subTest(operation=operation), self.assertRaisesMessage(ValidationError, "超级管理员账号受保护"):
                self.preview(operation, ids=[self.user.pk, self.admin.pk], roles=[self.role.pk])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_locked_dates_future_and_clear_including_superuser(self):
        profile = UserProfile.objects.create(user=self.user, locked=True, join_date=date(2026, 1, 1))
        self.save(self.preview("set_leave_date", ids=[self.user.pk, self.admin.pk], leave_date="2099-01-01"))
        profile.refresh_from_db()
        self.assertTrue(profile.locked)
        self.assertEqual(profile.leave_date, date(2099, 1, 1))
        self.save(self.preview("clear_leave_date", ids=[self.user.pk, self.admin.pk]))
        profile.refresh_from_db()
        self.assertIsNone(profile.leave_date)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_invalid_date_rejects_entire_batch(self):
        UserProfile.objects.create(user=self.other, join_date=date(2026, 2, 1))
        with self.assertRaisesMessage(ValidationError, "离开日期不能早于入读日期"):
            self.preview("set_leave_date", ids=[self.user.pk, self.other.pk], leave_date="2026-01-01")
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

    def test_empty_duplicate_missing_ids_and_invalid_payload(self):
        for ids in ([], ["bad"], [0], [999999]):
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                preview_users(actor=self.admin, ids=ids, payload=self.payload())
        self.assertEqual(self.preview(ids=[self.user.pk, self.user.pk])["count"], 1)
        for operation, kwargs in [
            ("invalid", {}),
            ("add_roles", {}),
            ("set_leave_date", {}),
            ("add_roles", {"roles": [999999]}),
        ]:
            with self.subTest(operation=operation), self.assertRaises(ValidationError):
                self.preview(operation, **kwargs)

    def test_stale_account_membership_direct_permissions_and_role_configuration(self):
        changes = [
            lambda: User.objects.filter(pk=self.user.pk).update(is_active=False),
            lambda: self.user.groups.add(self.existing),
            lambda: self.user.user_permissions.add(self.permission),
            lambda: self.role.permissions.add(self.permission),
        ]
        for change in changes:
            preview = self.preview("add_roles", roles=[self.role.pk])
            change()
            with self.assertRaisesMessage(ValidationError, "重新预览"):
                self.save(preview)
            self.assertFalse(self.user.groups.filter(pk=self.role.pk).exists())

    def test_stale_profile_date_and_missing_user(self):
        profile = UserProfile.objects.create(user=self.user, join_date=date(2026, 1, 1))
        preview = self.preview("set_leave_date", leave_date="2026-02-01")
        profile.join_date = date(2026, 1, 2)
        profile.save()
        with self.assertRaisesMessage(ValidationError, "重新预览"):
            self.save(preview)
        preview = self.preview()
        self.user.delete()
        with self.assertRaisesMessage(ValidationError, "已不存在"):
            self.save(preview)

    def test_expired_tampered_and_other_actor_token(self):
        preview = self.preview()
        with self.assertRaises(ValidationError):
            save_users(actor=self.admin, token=preview["token"] + "bad")
        with (
            patch("django.core.signing.time.time", return_value=99999999999),
            self.assertRaisesMessage(ValidationError, "预览已失效"),
        ):
            self.save(preview)
        other_admin = User.objects.create_superuser("other-admin", "other@example.com", "password")
        with self.assertRaisesMessage(ValidationError, "所属管理员"):
            save_users(actor=other_admin, token=preview["token"])

    def test_actor_revoked_after_preview(self):
        preview = self.preview()
        User.objects.filter(pk=self.admin.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            self.save(preview)

    def test_single_confirmation_rejects_token_for_another_target(self):
        preview = self.preview()
        url = reverse("accounts:user_manage_single", args=[self.other.pk])
        response = self.client.post(url, {"action": "save", "preview_token": preview["token"]})
        self.assertContains(response, "不一致", status_code=400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_reactivation_direct_save_preserves_existing_leave_date(self):
        profile = UserProfile.objects.create(user=self.other, leave_date=date(2026, 2, 1))
        self.other.is_active = True
        self.other.save(update_fields=["is_active"])
        profile.refresh_from_db()
        self.assertEqual(profile.leave_date, date(2026, 2, 1))

    def test_role_scope_changes_require_new_preview(self):
        from standards.models import SkillProject, TechnicalDomain, TechnicalDomainGroupScope

        project = SkillProject.objects.create(name="测试技能", code="bulk-test")
        domain = TechnicalDomain.objects.create(name="测试领域", code="bulk-domain", skill_project=project)
        preview = self.preview("add_roles", roles=[self.role.pk])
        TechnicalDomainGroupScope.objects.create(group=self.role, technical_domain=domain)
        with self.assertRaisesMessage(ValidationError, "重新预览"):
            self.save(preview)

    def test_new_profile_or_locked_date_change_invalidates_preview(self):
        preview = self.preview("set_leave_date", leave_date="2026-05-01")
        profile = UserProfile.objects.create(user=self.user, locked=True, leave_date=date(2026, 3, 1))
        with self.assertRaisesMessage(ValidationError, "重新预览"):
            self.save(preview)
        profile.refresh_from_db()
        self.assertEqual(profile.leave_date, date(2026, 3, 1))

    def test_batch_rolls_back_on_second_write_failure(self):
        preview = self.preview("add_roles", ids=[self.user.pk, self.other.pk], roles=[self.role.pk])
        manager_type = type(self.user.groups)
        original = manager_type.add
        calls = []

        def fail_second(manager, *args, **kwargs):
            calls.append(manager.instance.pk)
            if len(calls) == 2:
                raise RuntimeError("write failed")
            return original(manager, *args, **kwargs)

        with patch.object(manager_type, "add", fail_second), self.assertRaises(RuntimeError):
            self.save(preview)
        self.assertFalse(self.role.user_set.exists())

    def test_list_full_name_filters_pagination_and_htmx(self):
        self.user.groups.add(self.role)
        UserProfile.objects.create(user=self.user, student_id="S123")
        url = reverse("accounts:user_list")
        for query in ("张三", "student", "S123"):
            response = self.client.get(url, {"q": query, "active": "1", "role": self.role.pk})
            self.assertEqual(list(response.context["object_list"]), [self.user])
        response = self.client.get(url, {"role": "none", "active": "0"})
        self.assertEqual(list(response.context["object_list"]), [self.other])
        response = self.client.get(url, {"q": "张三"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, 'data-bulk-list')
        self.assertNotContains(response, 'id="list-results"')
        self.assertNotContains(response, "<!DOCTYPE", html=False)
        self.assertNotContains(response, "js/list-bulk-actions.js")
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIsNotNone(soup.select_one('input[name="users"]'))
        self.assertIsNotNone(soup.select_one('[data-select-all]'))

    def test_all_matching_freezes_targets_and_not_new_matches(self):
        users = [User.objects.create_user(f"batch-{index}") for index in range(25)]
        response = self.client.post(self.url, {"selection": "all", "q": "batch-", "operation": "deactivate"})
        self.assertEqual(response.context["preview"]["count"], 25)
        token = response.context["preview"]["token"]
        self.assertEqual(len(signing.loads(token, salt=SALT)["ids"]), 25)
        newcomer = User.objects.create_user("batch-new")
        response = self.client.post(self.url, {"action": "save", "preview_token": token})
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertEqual(User.objects.filter(pk__in=[user.pk for user in users], is_active=False).count(), 25)
        newcomer.refresh_from_db()
        self.assertTrue(newcomer.is_active)

    def test_invalid_filters_empty_selection_and_single_flow(self):
        for payload in [
            {"selection": "all", "active": "invalid"},
            {"selection": "all", "role": "999999"},
            {"selection": "selected"},
            {"selection": "invalid"},
        ]:
            response = self.client.post(self.url, {"operation": "deactivate", **payload})
            self.assertEqual(response.status_code, 400)
        url = reverse("accounts:user_manage_single", args=[self.user.pk])
        self.assertContains(self.client.get(url), "张三")
        response = self.client.post(url, {"operation": "deactivate"})
        token = response.context["preview"]["token"]
        response = self.client.post(url, {"action": "save", "preview_token": token})
        self.assertRedirects(response, reverse("accounts:user_detail", args=[self.user.pk]))

    def test_permissions_csrf_and_read_only_list(self):
        for is_staff in (False, True):
            user = User.objects.create_user(f"viewer-{is_staff}", is_staff=is_staff)
            user.user_permissions.add(
                Permission.objects.get(codename="view_all_profiles", content_type__app_label="accounts")
            )
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url, {"selection": "all", "operation": "activate"}).status_code, 403)
            self.assertEqual(
                self.client.get(reverse("accounts:user_manage_single", args=[self.user.pk])).status_code, 403
            )
            response = self.client.get(reverse("accounts:user_list"))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "data-row-selection")
            self.assertNotContains(response, "批量管理")
        anonymous = Client()
        self.assertIn(anonymous.post(self.url).status_code, (302, 403))
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(self.url, {"selection": "all", "operation": "activate"}).status_code, 403)

    def test_compact_actions_keep_filters_and_move_parameters_out_of_list(self):
        response = self.client.get(reverse("accounts:user_list"), {"q": "张三", "sort": "first_name"})
        self.assertContains(response, "js/list-bulk-actions.js")
        soup = BeautifulSoup(response.content, "html.parser")
        form = soup.select_one("[data-bulk-list]")
        self.assertIsNotNone(form.select_one("thead [data-select-page]"))
        self.assertIsNone(form.select_one('[name="roles"]'))
        self.assertIsNone(form.select_one('[name="leave_date"]'))
        self.assertEqual(form.select_one('[name="operation"] option')["value"], "")
        self.assertTrue(form.select_one('[data-select-all]').has_attr("hidden"))
        self.assertTrue(form.select_one('[data-clear-selection]').has_attr("hidden"))
        self.assertIsNotNone(soup.select_one('input.list-filter-search[name="q"]'))
        self.assertEqual(form.select_one('[name="q"]')["value"], "张三")
        self.assertIn("sort=first_name", form.select_one('[name="return_query"]')["value"])

    def test_parameter_page_freezes_all_matching_before_parameters_are_entered(self):
        response = self.client.post(
            self.url,
            {
                "selection": "all",
                "q": "student",
                "operation": "add_roles",
                "return_query": "q=student&sort=-first_name&page=1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("preview", response.context)
        selection = response.context["parameter_selection"]
        self.assertEqual([user.pk for user in selection["users"]], [self.user.pk])
        self.assertContains(response, "张三")
        self.assertContains(response, 'name="roles"')
        self.assertNotContains(response, 'name="leave_date"')
        self.assertFalse(self.user.groups.exists())
        newcomer = User.objects.create_user("student-new")
        response = self.client.post(
            self.url,
            {
                "parameter_token": selection["token"],
                "operation": "add_roles",
                "roles": [self.role.pk],
                "selection": "all",
                "q": "",
                "users": [newcomer.pk],
            },
        )
        preview = response.context["preview"]
        self.assertEqual(preview["count"], 1)
        self.assertEqual(response.context["return_query"], "q=student&sort=-first_name&page=1")
        response = self.client.post(
            self.url,
            {
                "action": "save",
                "preview_token": preview["token"],
                "return_query": response.context["return_query"],
            },
        )
        self.assertRedirects(response, reverse("accounts:user_list") + "?q=student&sort=-first_name&page=1")
        self.assertTrue(self.user.groups.filter(pk=self.role.pk).exists())
        self.assertFalse(newcomer.groups.exists())

    def test_parameter_validation_preserves_fixed_list_and_input(self):
        response = self.client.post(
            self.url,
            {
                "selection": "selected",
                "users": [self.user.pk],
                "operation": "set_leave_date",
            },
        )
        token = response.context["parameter_selection"]["token"]
        self.assertNotContains(response, 'name="roles"')
        self.assertContains(response, 'name="leave_date"')
        response = self.client.post(
            self.url,
            {
                "parameter_token": token,
                "operation": "set_leave_date",
                "leave_date": "invalid",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context["form"].errors["leave_date"])
        self.assertEqual(response.context["parameter_selection"]["token"], token)
        response = self.client.post(
            self.url,
            {
                "parameter_token": token,
                "operation": "set_leave_date",
                "leave_date": "2099-01-01",
            },
        )
        self.assertEqual(response.context["preview"]["rows"][0]["after"], "2099-01-01")
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

    def test_parameter_tokens_reject_tampering_expiry_and_operation_changes(self):
        response = self.client.post(
            self.url,
            {
                "selection": "selected",
                "users": [self.user.pk],
                "operation": "remove_roles",
            },
        )
        token = response.context["parameter_selection"]["token"]
        for submitted in (
            {"parameter_token": token + "bad", "operation": "remove_roles"},
            {"parameter_token": token, "operation": "activate"},
        ):
            self.assertEqual(self.client.post(self.url, submitted).status_code, 400)
        with patch("django.core.signing.time.time", return_value=time() + 1801):
            self.assertEqual(
                self.client.post(self.url, {"parameter_token": token, "operation": "remove_roles"}).status_code, 400
            )
        other_admin = User.objects.create_superuser("parameter-admin", "params@example.com", None)
        self.client.force_login(other_admin)
        response = self.client.post(self.url, {"parameter_token": token, "operation": "remove_roles"})
        self.assertContains(response, "所属管理员已变化", status_code=400)

    def test_parameter_page_rejects_deleted_targets_and_protected_users(self):
        response = self.client.post(
            self.url,
            {
                "selection": "selected",
                "users": [self.user.pk],
                "operation": "remove_roles",
            },
        )
        token = response.context["parameter_selection"]["token"]
        self.user.delete()
        response = self.client.post(
            self.url, {"parameter_token": token, "operation": "remove_roles", "roles": [self.role.pk]}
        )
        self.assertContains(response, "部分用户已不存在", status_code=400)
        response = self.client.post(
            self.url,
            {
                "selection": "selected",
                "users": [self.admin.pk],
                "operation": "add_roles",
            },
        )
        self.assertContains(response, "超级管理员账号受保护", status_code=400)

    def test_missing_operation_and_selection_have_chinese_feedback(self):
        response = self.client.post(self.url, {"selection": "selected", "users": [self.user.pk]})
        self.assertContains(response, "请选择要执行的操作", status_code=400)
        response = self.client.post(self.url, {"operation": "activate", "selection": "selected"})
        self.assertContains(response, "请至少选择一位用户", status_code=400)

    def test_cancel_and_save_restore_local_list_location_without_open_redirect(self):
        query = "q=student&active=1&sort=-first_name&page=1&next=https%3A%2F%2Fexample.com"
        response = self.client.post(
            self.url,
            {
                "selection": "selected",
                "users": [self.user.pk],
                "operation": "clear_leave_date",
                "return_query": query,
            },
        )
        expected = reverse("accounts:user_list") + "?q=student&active=1&sort=-first_name&page=1"
        self.assertEqual(response.context["return_url"], expected)
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIsNotNone(soup.find("a", href=expected))
        response = self.client.post(
            self.url,
            {
                "action": "save",
                "preview_token": response.context["preview"]["token"],
                "return_query": query,
            },
        )
        self.assertRedirects(response, expected)

    def test_save_clamps_page_when_action_shrinks_filtered_results(self):
        users = [User.objects.create_user(f"paged-{index}") for index in range(21)]
        response = self.client.post(
            self.url,
            {
                "selection": "all",
                "q": "paged-",
                "active": "1",
                "operation": "deactivate",
                "return_query": "q=paged-&active=1&sort=first_name&page=2",
            },
        )
        response = self.client.post(
            self.url,
            {
                "action": "save",
                "preview_token": response.context["preview"]["token"],
                "return_query": "q=paged-&active=1&sort=first_name&page=2",
            },
        )
        self.assertRedirects(response, reverse("accounts:user_list") + "?q=paged-&active=1&sort=first_name&page=1")
        self.assertEqual(User.objects.filter(pk__in=[user.pk for user in users], is_active=False).count(), 21)
