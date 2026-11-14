import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from urllib.parse import urlsplit
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import DisallowedHost, PermissionDenied
from django.db import close_old_connections, connections
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from accounts.models import PasswordResetGrant, UserProfile
from accounts.password_views import admin_password_reset_issue
from accounts.services.password_reset import consume_password_reset_grant, issue_password_reset_grant
from accounts.services.user_management import preview_users, save_users

User = get_user_model()
OLD_PASSWORD = "Original-Sample-168!"
NEW_PASSWORD = "Replacement-Sample-729!"
PASSWORD_DATA = {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}


class PasswordResetTests(TestCase):
    def setUp(self):
        self.issuer = User.objects.create_superuser("issuer", password=OLD_PASSWORD)
        self.user = User.objects.create_user("learner", first_name="学员", password=OLD_PASSWORD)
        self.issue_url = reverse("accounts:admin_password_reset_issue", args=[self.user.pk])

    def issue(self, user=None):
        return issue_password_reset_grant(
            actor=self.issuer, target_user_id=(user or self.user).pk, identity_verified=True,
        )

    def reset_url(self, grant):
        return reverse("accounts:password_reset_grant", args=[grant.pk])

    def assert_private(self, response, referrer_policy="same-origin"):
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], referrer_policy)
        self.assertEqual(response["Pragma"], "no-cache")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_issue_requires_active_superuser_and_distinct_active_target(self):
        data = {"identity_verified": "on"}
        self.assertEqual(self.client.post(self.issue_url, data, secure=True).status_code, 302)
        self.user.user_permissions.add(Permission.objects.get(codename="view_all_profiles"))
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(self.issue_url, data, secure=True).status_code, 403)
        self.client.force_login(self.issuer)
        self.assertEqual(self.client.get(self.issue_url, secure=True).status_code, 405)
        self.assertEqual(self.client.post(reverse(
            "accounts:admin_password_reset_issue", args=[self.issuer.pk],
        ), data, secure=True).status_code, 403)
        self.assertEqual(self.client.post(reverse(
            "accounts:admin_password_reset_issue", args=[999999],
        ), data, secure=True).status_code, 404)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.client.post(self.issue_url, data, secure=True).status_code, 403)
        self.issuer.is_active = False
        self.issuer.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.issue()
        self.assertFalse(PasswordResetGrant.objects.exists())

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
    def test_issue_response_and_origin(self):
        self.client.force_login(self.issuer)
        data = {"identity_verified": "on", "reason": "当面核验", "host": "attacker.invalid"}
        self.assertEqual(self.client.post(self.issue_url, data).status_code, 403)
        self.assertEqual(self.client.post(self.issue_url, {}, secure=True).status_code, 400)
        request = RequestFactory().post(self.issue_url, data, secure=True, HTTP_HOST="attacker.invalid")
        request.user = self.issuer
        request._dont_enforce_csrf_checks = True
        with self.assertRaises(DisallowedHost):
            admin_password_reset_issue(request, self.user.pk)
        self.assertFalse(PasswordResetGrant.objects.exists())
        response = self.client.post(self.issue_url, data, secure=True)
        self.assert_private(response, referrer_policy="no-referrer")
        link = urlsplit(response.context["reset_link"])
        grant = PasswordResetGrant.objects.get()
        self.assertEqual((link.scheme, link.netloc, link.path, link.query), (
            "https", "testserver", self.reset_url(grant), "",
        ))
        self.assertEqual(len(link.fragment), 43)
        self.assertEqual(grant.token_digest, hashlib.sha256(link.fragment.encode()).hexdigest())
        self.assertEqual((grant.issued_by, grant.user, grant.reason), (self.issuer, self.user, "当面核验"))
        self.assertAlmostEqual((grant.expires_at - grant.created_at).total_seconds(), 1800, delta=1)
        self.assertNotContains(self.client.get(reverse("accounts:user_detail", args=[self.user.pk])), link.fragment)
        self.assertNotIn(link.fragment, repr(dict(self.client.session)))

    def test_reissue_and_successful_reset(self):
        other = User.objects.create_superuser("other", password=OLD_PASSWORD)
        independent, _ = self.issue(other)
        previous, _ = self.issue()
        PasswordResetGrant.objects.filter(pk=previous.pk).update(expires_at=timezone.now() - timedelta(seconds=1),
                                                                  created_at=timezone.now() - timedelta(hours=1))
        grant, token = self.issue()
        previous.refresh_from_db()
        self.assertIsNotNone(previous.revoked_at)
        anonymous = Client()
        old_session = Client()
        old_session.force_login(self.user)
        for _ in range(2):
            response = anonymous.get(self.reset_url(grant), secure=True)
            self.assert_private(response)
            self.assertContains(response, 'name="new_password1"')
            self.assertNotContains(response, token)
        grant.refresh_from_db()
        self.assertIsNone(grant.used_at)
        self.assertIsNone(grant.revoked_at)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password(OLD_PASSWORD))

        response = anonymous.post(self.reset_url(grant), {"token": token, **PASSWORD_DATA}, secure=True)
        self.assert_private(response)
        self.assertContains(response, "密码已重置")
        self.assertNotContains(response, token)
        self.assertNotIn("_auth_user_id", anonymous.session)
        self.assertEqual(old_session.get(reverse("accounts:profile")).status_code, 302)
        self.assertFalse(anonymous.login(username=self.user.username, password=OLD_PASSWORD))
        self.assertTrue(anonymous.login(username=self.user.username, password=NEW_PASSWORD))
        grant.refresh_from_db()
        independent.refresh_from_db()
        self.assertIsNotNone(grant.used_at)
        self.assertIsNone(independent.revoked_at)
        self.assertTrue(User.objects.get(pk=other.pk).check_password(OLD_PASSWORD))
        self.assertContains(
            anonymous.post(self.reset_url(grant), {"token": token, **PASSWORD_DATA}, secure=True), "链接不可用",
        )

    def test_invalid_password_can_be_retried_but_invalid_token_never_changes_grant(self):
        grant, token = self.issue()
        url = self.reset_url(grant)
        for invalid_token in ("", "x" * 43):
            response = self.client.post(url, {"token": invalid_token, **PASSWORD_DATA}, secure=True)
            self.assertContains(response, "链接不可用")
        for password, confirmation in ((NEW_PASSWORD, "different"), ("12345678", "12345678")):
            response = self.client.post(url, {
                "token": token, "new_password1": password, "new_password2": confirmation,
            }, secure=True)
            self.assert_private(response)
            self.assertTrue(response.context["form"].errors)
            self.assertContains(response, f'name="token" value="{token}"')
            self.assertNotContains(response, f'value="{password}"')
        grant.refresh_from_db()
        self.assertIsNone(grant.used_at)
        self.assertIsNone(grant.revoked_at)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password(OLD_PASSWORD))
        self.assertContains(self.client.post(url, {"token": token, **PASSWORD_DATA}, secure=True), "密码已重置")

    def test_expired_revoked_and_missing_grants(self):
        grant, token = self.issue()
        older = timezone.now() - timedelta(hours=1)
        PasswordResetGrant.objects.filter(pk=grant.pk).update(
            created_at=older, expires_at=older + timedelta(minutes=30),
        )
        for grant_id, raw_token in ((uuid4(), token), (grant.pk, token)):
            url = reverse("accounts:password_reset_grant", args=[grant_id])
            self.assertContains(self.client.get(url, secure=True), "链接不可用")
            self.assertContains(self.client.post(url, {"token": raw_token, **PASSWORD_DATA}, secure=True), "链接不可用")
        revoked, revoked_token = self.issue()
        active, _ = self.issue()
        self.assertContains(self.client.get(self.reset_url(revoked), secure=True), "链接不可用")
        self.assertContains(self.client.post(
            self.reset_url(revoked), {"token": revoked_token, **PASSWORD_DATA}, secure=True,
        ), "链接不可用")
        self.assertContains(self.client.get(self.reset_url(active), secure=True), 'name="new_password1"')

    def test_inactive_target_or_ineligible_issuer_cannot_reset(self):
        grant, token = self.issue()
        url = self.reset_url(grant)
        for user, field in ((self.user, "is_active"), (self.issuer, "is_superuser"), (self.issuer, "is_active")):
            setattr(user, field, False)
            user.save(update_fields=[field])
            self.assertContains(self.client.get(url, secure=True), "链接不可用")
            self.assertContains(self.client.post(url, {"token": token, **PASSWORD_DATA}, secure=True), "链接不可用")
            setattr(user, field, True)
            user.save(update_fields=[field])

    def test_external_password_change_invalidates_grant(self):
        grant, token = self.issue()
        self.user.set_password("Changed-Outside-Reset-923!")
        self.user.save(update_fields=["password"])
        self.assertContains(self.client.get(self.reset_url(grant), secure=True), "链接不可用")
        self.assertContains(self.client.post(
            self.reset_url(grant), {"token": token, **PASSWORD_DATA}, secure=True,
        ), "链接不可用")

    def test_account_deactivation_revokes_link_even_after_reactivation(self):
        grant, token = self.issue()
        for operation in ("deactivate", "activate"):
            preview = preview_users(
                actor=self.issuer, ids=[self.user.pk],
                payload={"operation": operation, "roles": [], "leave_date": ""},
            )
            save_users(actor=self.issuer, token=preview["token"])
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoked_at)
        self.assertContains(self.client.post(
            self.reset_url(grant), {"token": token, **PASSWORD_DATA}, secure=True,
        ), "链接不可用")

    @override_settings(
        DEBUG=False, SECURE_SSL_REDIRECT=False, SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    )
    def test_trusted_proxy_uses_https_origin(self):
        self.client.force_login(self.issuer)
        response = self.client.post(self.issue_url, {"identity_verified": "on"}, HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(urlsplit(response.context["reset_link"]).scheme, "https")

    def test_csrf_protects_both_post_routes(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.issuer)
        self.assertEqual(client.post(self.issue_url, {"identity_verified": "on"}, secure=True).status_code, 403)
        grant, token = self.issue()
        client.logout()
        self.assertEqual(client.post(
            self.reset_url(grant), {"token": token, **PASSWORD_DATA}, secure=True,
        ).status_code, 403)

    @override_settings(DEBUG=True)
    def test_reset_form_accepts_same_origin_post_with_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        for secure in (False, True):
            grant, token = self.issue()
            url = self.reset_url(grant)
            page = client.get(url, secure=secure)
            self.assert_private(page)
            self.assertContains(page, 'name="csrfmiddlewaretoken"')
            data = {"token": token, "csrfmiddlewaretoken": client.cookies["csrftoken"].value}
            origin = "https://testserver" if secure else "http://testserver"
            rejected = client.post(url, {**data, **PASSWORD_DATA}, secure=secure, HTTP_ORIGIN="null")
            self.assertEqual(rejected.status_code, 403)
            retry = client.post(url, {**data, **PASSWORD_DATA, "new_password2": "different"},
                                secure=secure, HTTP_ORIGIN=origin)
            self.assert_private(retry)
            self.assertTrue(retry.context["form"].errors)
            success = client.post(url, {**data, **PASSWORD_DATA}, secure=secure, HTTP_ORIGIN=origin)
            self.assertContains(success, "密码已重置")

    def test_self_change_keeps_current_session_and_revokes_grant(self):
        grant, _ = self.issue()
        UserProfile.objects.update_or_create(user=self.user, defaults={"locked": True})
        self.client.force_login(self.user)
        other_session = Client()
        other_session.force_login(self.user)
        url = reverse("accounts:password_change")
        self.assertContains(self.client.get(url), 'name="old_password"')
        for data in (
            {"old_password": "wrong", **PASSWORD_DATA},
            {"old_password": OLD_PASSWORD, "new_password1": "12345678", "new_password2": "12345678"},
        ):
            self.assertTrue(self.client.post(url, data).context["form"].errors)
        self.assertTrue(User.objects.get(pk=self.user.pk).check_password(OLD_PASSWORD))
        self.assertRedirects(self.client.post(url, {"old_password": OLD_PASSWORD, **PASSWORD_DATA}),
                             reverse("accounts:password_change_done"))
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
        self.assertEqual(other_session.get(reverse("accounts:profile")).status_code, 302)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoked_at)


@skipUnlessDBFeature("has_select_for_update")
class PasswordResetConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.issuer = User.objects.create_superuser("issuer", password=OLD_PASSWORD)
        self.user = User.objects.create_user("learner", password=OLD_PASSWORD)

    def issue(self):
        return issue_password_reset_grant(
            actor=self.issuer, target_user_id=self.user.pk, identity_verified=True,
        )

    def concurrently(self, first, second):
        barrier = Barrier(2, timeout=10)

        def run(operation):
            close_old_connections()
            try:
                barrier.wait()
                return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(run, operation) for operation in (first, second)]
            return [result.result(timeout=20) for result in results]

    def test_same_grant_can_only_be_consumed_once(self):
        grant, token = self.issue()

        def consume():
            return consume_password_reset_grant(grant_id=grant.pk, raw_token=token, data=PASSWORD_DATA)

        self.assertEqual(sum(result is not None for result in self.concurrently(consume, consume)), 1)

    def test_concurrent_issuance_leaves_one_open_grant(self):
        self.concurrently(self.issue, self.issue)
        self.assertEqual(PasswordResetGrant.objects.count(), 2)
        self.assertEqual(PasswordResetGrant.objects.filter(revoked_at__isnull=True).count(), 1)

    def test_concurrent_issuance_and_consumption(self):
        grant, token = self.issue()

        def consume():
            return consume_password_reset_grant(grant_id=grant.pk, raw_token=token, data=PASSWORD_DATA)

        (new_grant, _), consumed = self.concurrently(self.issue, consume)
        grant.refresh_from_db()
        self.assertEqual(grant.used_at is not None, consumed is not None)
        self.assertEqual(grant.revoked_at is not None, consumed is None)
        self.assertEqual(PasswordResetGrant.objects.get(used_at=None, revoked_at=None).pk, new_grant.pk)
