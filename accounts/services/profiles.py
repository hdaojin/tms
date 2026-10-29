"""本人和管理员资料写入入口；锁定后的完整资料必须先解锁。"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.forms import ProfileForm
from accounts.models import UserProfile


@transaction.atomic
def update_profile(*, actor, target_id, action, data):
    users = {
        user.pk: user
        for user in get_user_model()
        .objects.select_for_update()
        .filter(
            pk__in={actor.pk, target_id},
        )
        .order_by("pk")
    }
    operator = users.get(actor.pk)
    if not operator or not operator.is_active or (operator.pk != target_id and not operator.is_superuser):
        raise PermissionDenied
    if action == "unlock" and not operator.is_superuser:
        raise PermissionDenied
    if action not in ("save", "lock", "unlock"):
        raise ValidationError("不支持的资料操作。")
    target = users[target_id]
    profile, _ = UserProfile.objects.select_for_update().get_or_create(user=target)
    if action == "unlock":
        profile.locked = False
        profile.save(update_fields=["locked"])
        return None
    if profile.locked:
        raise ValidationError("资料已锁定，请先由管理员解锁后再修改。")

    form = ProfileForm(data, instance=profile)
    if not form.is_valid():
        return form
    target.email = form.cleaned_data["email"]
    target.save(update_fields=["email"])
    profile = form.save(commit=False)
    if action == "lock":
        profile.locked = True
    profile.save()
    return form
