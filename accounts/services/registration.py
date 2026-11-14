from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, F, Q, Value, When
from django.db.models.functions import Now
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from accounts.models import RegistrationInvitation, RegistrationInvitationUse, RegistrationSubmissionWindow, UserProfile
from core.models import SiteConfig
from core.utils.invitation import generate_invitation_code, invitation_code_digest

DEFAULT_INVITATION_HOURS = 2
MAX_INVITATION_HOURS = 24
MAX_INVITATION_USES = 50
INVALID_INVITATION = "邀请码无效、已过期或已用完，请联系管理员。"
REGISTRATION_SUBMISSIONS_PER_MINUTE = 120


def apply_default_registration_group(user) -> None:
    default_group = SiteConfig.get_solo().default_registration_group
    if default_group is not None:
        user.groups.add(default_group)


def require_invitation_manager(actor):
    if not (actor.is_active and actor.is_superuser):
        raise PermissionDenied


@sensitive_variables("code")
def issue_registration_invitation(*, actor, hours, max_uses):
    require_invitation_manager(actor)
    if not 1 <= hours <= MAX_INVITATION_HOURS or not 1 <= max_uses <= MAX_INVITATION_USES:
        raise ValidationError("有效期须为 1～24 小时，名额须为 1～50 人。")
    code = generate_invitation_code()
    invitation = RegistrationInvitation.objects.create(
        code_digest=invitation_code_digest(code),
        expires_at=timezone.now() + timedelta(hours=hours),
        max_uses=max_uses,
        created_by=actor,
        updated_by=actor,
    )
    return invitation, code


def revoke_registration_invitation(*, actor, invitation_id):
    require_invitation_manager(actor)
    now = timezone.now()
    return RegistrationInvitation.objects.filter(pk=invitation_id, revoked_at__isnull=True).update(
        revoked_at=now, updated_at=now, updated_by=actor,
    )


def allow_registration_submission():
    now = timezone.now()
    expired = Q(started_at__lte=now - timedelta(minutes=1))
    windows = RegistrationSubmissionWindow.objects.filter(pk=1)
    if not windows.exists():
        RegistrationSubmissionWindow.objects.get_or_create(pk=1, defaults={"started_at": now})
    return bool(windows.filter(expired | Q(submissions__lt=REGISTRATION_SUBMISSIONS_PER_MINUTE)).update(
        started_at=Case(When(expired, then=Value(now)), default=F("started_at")),
        submissions=Case(When(expired, then=Value(1)), default=F("submissions") + 1),
        updated_at=now,
    ))


@sensitive_variables("code")
@transaction.atomic
def register_invited_user(*, user, code):
    invitations = RegistrationInvitation.objects.filter(code_digest=invitation_code_digest(code))
    if not invitations.filter(
        revoked_at__isnull=True, expires_at__gt=Now(), used_count__lt=F("max_uses"),
    ).update(used_count=F("used_count") + 1, updated_at=Now()):
        raise ValidationError(INVALID_INVITATION)

    user.is_active = False
    user.save()
    UserProfile.objects.get_or_create(user=user)
    apply_default_registration_group(user)
    RegistrationInvitationUse.objects.create(invitation=invitations.get(), user=user)
    return user
