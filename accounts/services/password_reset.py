import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.debug import sensitive_variables

from accounts.forms import StyledPasswordChangeForm, StyledSetPasswordForm
from accounts.models import PasswordResetGrant

User = get_user_model()
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


def can_issue_password_reset(actor, target):
    return actor.is_active and actor.is_superuser and target.is_active and actor.pk != target.pk


def revoke_password_reset_grants(user_id):
    now = timezone.now()
    PasswordResetGrant.objects.filter(
        user_id=user_id, used_at__isnull=True, revoked_at__isnull=True,
    ).update(revoked_at=now, updated_at=now)


def _password_fingerprint(user):
    return salted_hmac("accounts.password-reset", user.password, algorithm="sha256").hexdigest()


def _locked_users(*user_ids):
    # 先按主键顺序锁定涉及的用户，再锁定或更新授权。
    return {
        user.pk: user
        for user in User.objects.select_for_update().filter(pk__in=user_ids).order_by("pk")
    }


@sensitive_variables()
@transaction.atomic
def issue_password_reset_grant(*, actor, target_user_id, identity_verified, reason=""):
    users = _locked_users(actor.pk, target_user_id)
    issuer, target = users.get(actor.pk), users.get(target_user_id)
    if issuer is None or target is None or not can_issue_password_reset(issuer, target):
        raise PermissionDenied
    if identity_verified is not True or len(reason) > 200:
        raise ValidationError("请确认已核实用户身份，核验备注不得超过 200 字。")

    revoke_password_reset_grants(target.pk)
    raw_token = secrets.token_urlsafe(32)
    grant = PasswordResetGrant.objects.create(
        user=target,
        issued_by=issuer,
        token_digest=hashlib.sha256(raw_token.encode()).hexdigest(),
        password_fingerprint=_password_fingerprint(target),
        expires_at=timezone.now() + timedelta(minutes=30),
        reason=reason,
    )
    return grant, raw_token


def _is_usable(grant, user, issuer):
    return (
        grant is not None
        and user is not None
        and issuer is not None
        and can_issue_password_reset(issuer, user)
        and grant.used_at is None
        and grant.revoked_at is None
        and grant.expires_at > timezone.now()
        and hmac.compare_digest(grant.password_fingerprint, _password_fingerprint(user))
    )


def password_reset_form(grant_id):
    grant = PasswordResetGrant.objects.select_related("user", "issued_by").filter(pk=grant_id).first()
    if grant and _is_usable(grant, grant.user, grant.issued_by):
        return StyledSetPasswordForm(grant.user)
    return None


@sensitive_variables()
@transaction.atomic
def consume_password_reset_grant(*, grant_id, raw_token, data):
    """返回校验失败的表单或已使用的授权。不可用时返回 None。"""
    if not raw_token or not TOKEN_PATTERN.fullmatch(raw_token):
        return None
    owners = PasswordResetGrant.objects.filter(pk=grant_id).values_list("user_id", "issued_by_id").first()
    if owners is None:
        return None
    user_id, issuer_id = owners
    users = _locked_users(user_id, issuer_id)
    user, issuer = users.get(user_id), users.get(issuer_id)
    grant = PasswordResetGrant.objects.select_for_update().filter(pk=grant_id, issued_by_id=issuer_id).first()
    if not _is_usable(grant, user, issuer):
        return None
    if not hmac.compare_digest(grant.token_digest, hashlib.sha256(raw_token.encode()).hexdigest()):
        return None
    form = StyledSetPasswordForm(user, data=data)
    if not form.is_valid():
        return form
    form.save(commit=False).save(update_fields=["password"])
    grant.used_at = timezone.now()
    grant.save(update_fields=["used_at", "updated_at"])
    revoke_password_reset_grants(user.pk)
    return grant


@sensitive_variables()
@transaction.atomic
def change_own_password(*, user_id, data):
    user = _locked_users(user_id).get(user_id)
    if user is None or not user.is_active:
        raise PermissionDenied
    form = StyledPasswordChangeForm(user, data=data)
    if form.is_valid():
        form.save(commit=False).save(update_fields=["password"])
        revoke_password_reset_grants(user.pk)
    return form
