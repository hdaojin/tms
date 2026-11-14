from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RegistrationInvitation
from accounts.services.registration import issue_registration_invitation, register_invited_user
from core.utils.invitation import invitation_code_digest

User = get_user_model()


class InvitationCodeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("invitation-admin")

    def issue(self, max_uses=1):
        return issue_registration_invitation(actor=self.admin, hours=2, max_uses=max_uses)

    def test_independent_codes_and_quota(self):
        invitation, code = self.issue(max_uses=2)
        other, other_code = self.issue()
        self.assertEqual(len(code), 43)
        self.assertEqual(invitation.code_digest, invitation_code_digest(code))
        self.assertNotEqual(other_code, code)

        for username in ("first", "second"):
            user = register_invited_user(user=User(username=username), code=code)
            self.assertFalse(user.is_active)
        with self.assertRaises(ValidationError):
            register_invited_user(user=User(username="third"), code=code)
        invitation.refresh_from_db()
        self.assertEqual(invitation.used_count, 2)
        self.assertEqual(invitation.registrations.count(), 2)

        register_invited_user(user=User(username="third"), code=other_code)
        other.refresh_from_db()
        self.assertEqual(other.used_count, 1)

    def test_failed_registration_rolls_back_quota_and_user(self):
        invitation, code = self.issue()
        with patch("accounts.services.registration.apply_default_registration_group", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                register_invited_user(user=User(username="rollback"), code=code)
        invitation.refresh_from_db()
        self.assertEqual(invitation.used_count, 0)
        self.assertFalse(User.objects.filter(username="rollback").exists())
        self.assertFalse(invitation.registrations.exists())

    def test_expired_revoked_and_legacy_codes_are_rejected(self):
        expired, expired_code = self.issue()
        expired.expires_at = timezone.now() - timedelta(seconds=1)
        expired.save(update_fields=["expires_at", "updated_at"])
        revoked, revoked_code = self.issue()
        revoke_url = reverse("accounts:revoke_invitation", args=[revoked.pk])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(revoke_url).status_code, 405)
        self.assertRedirects(self.client.post(revoke_url), reverse("accounts:generate_invitation"))

        invalid_codes = [
            expired_code, revoked_code, "invalid",
            signing.dumps({"type": "invite"}, salt="invitation-code-v1"),
            signing.TimestampSigner(salt="invitation-code-v2").sign("2"),
        ]
        for code in invalid_codes:
            with self.subTest(code_type=len(code)), self.assertRaises(ValidationError):
                register_invited_user(user=User(username="rejected"), code=code)

    def test_issue_validates_limits_and_permissions(self):
        url = reverse("accounts:generate_invitation")
        self.client.force_login(User.objects.create_user("ordinary"))
        self.assertEqual(self.client.post(url, {"hours": 2, "max_uses": 1}).status_code, 302)
        self.client.force_login(self.admin)
        self.assertContains(self.client.post(url, {"hours": 25, "max_uses": 51}), "error")
        self.assertFalse(RegistrationInvitation.objects.exists())

    def test_cli_uses_same_issuance_service(self):
        output = StringIO()
        call_command("generate_invite", actor_id=self.admin.pk, stdout=output)
        code = output.getvalue().strip()
        invitation = RegistrationInvitation.objects.get()
        self.assertEqual(invitation.code_digest, invitation_code_digest(code))
        self.assertEqual(invitation.created_by, self.admin)

    @patch("accounts.services.registration.REGISTRATION_SUBMISSIONS_PER_MINUTE", 2)
    def test_throttle_rejects_submissions_until_window_resets(self):
        url = reverse("accounts:signup")
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 200)
        response = self.client.post(url)
        self.assertContains(response, "请稍后重试", status_code=429)
        self.assertEqual(response["Retry-After"], "60")
        with patch("accounts.services.registration.timezone.now", return_value=timezone.now() + timedelta(minutes=1)):
            self.assertEqual(self.client.post(url).status_code, 200)
