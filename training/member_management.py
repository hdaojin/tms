"""周期成员批量添加的固定名单、预览与事务确认。"""

from django import forms
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.services.user_management import normalize_ids
from accounts.services.users import get_user_display_name
from core.utils.forms import StyledFormMixin

from .models import TrainingCycle, TrainingCycleMember
from .services import save_cycle_member

SALT = "training.cycle-member-add"
User = get_user_model()


class MemberActionForm(StyledFormMixin, forms.Form):
    operation = forms.ChoiceField(
        label="操作", choices=[("", "请选择操作"), ("add", "添加周期成员")],
        widget=forms.Select(attrs={"data-bulk-operation": ""}),
    )


def _require_permissions(actor, *, is_current=False):
    actor = User.objects.get(pk=actor.pk)
    permissions = ["training.view_trainingcyclemember", "training.add_trainingcyclemember"]
    if is_current:
        permissions.append("training.change_trainingcyclemember")
    if not actor.is_active or not actor.has_perms(permissions):
        raise PermissionDenied


def _state(cycle, ids):
    users = list(User.objects.filter(pk__in=ids).order_by("pk"))
    if len(users) != len(ids) or any(not user.is_active for user in users):
        raise ValidationError("部分用户已不存在或已停用，请重新选择。")
    memberships = list(TrainingCycleMember.objects.filter(user_id__in=ids).order_by("pk").values_list(
        "pk", "user_id", "training_cycle_id", "role", "is_current",
    ))
    if any(row[2] == cycle.pk for row in memberships):
        raise ValidationError("部分用户已加入本周期，请重新选择。")
    return users, {
        "cycle": [cycle.status, cycle.start_date.isoformat(), cycle.end_date.isoformat() if cycle.end_date else None],
        "users": [[user.pk, user.username, user.last_name, user.first_name] for user in users],
        "memberships": [list(row) for row in memberships],
    }


def prepare_member_add(*, actor, cycle, ids, return_query):
    _require_permissions(actor)
    ids = normalize_ids(ids)
    cycle.refresh_from_db()
    users, state = _state(cycle, ids)
    token = signing.dumps({
        "actor": actor.pk, "cycle": cycle.pk, "ids": ids, "state": state,
        "return_query": return_query, "stage": "parameters",
    }, salt=SALT, compress=True)
    return {"token": token, "users": users, "return_query": return_query}


def load_member_add(*, actor, cycle, token, stage):
    _require_permissions(actor)
    try:
        data = signing.loads(token, salt=SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError("操作已过期或无效，请返回列表重新选择。") from exc
    if data["actor"] != actor.pk or data["cycle"] != cycle.pk or data["stage"] != stage:
        raise ValidationError("操作名单与当前页面不符，请重新选择。")
    cycle.refresh_from_db()
    users, state = _state(cycle, data["ids"])
    if data["state"] != state:
        raise ValidationError("周期或所选用户的成员状态已变化，请返回列表重新预览。")
    return data, users


def preview_member_add(*, actor, cycle, token, role, is_current):
    data, users = load_member_add(actor=actor, cycle=cycle, token=token, stage="parameters")
    _require_permissions(actor, is_current=is_current)
    rows = []
    current_names = dict(TrainingCycleMember.objects.filter(user_id__in=data["ids"], is_current=True)
                         .values_list("user_id", "training_cycle__name"))
    for user in users:
        member = TrainingCycleMember(training_cycle=cycle, user=user, role=role, is_current=is_current)
        member.clean()
        rows.append({"name": get_user_display_name(user), "username": user.username,
                     "before": current_names.get(user.pk, "未设置"),
                     "after": cycle.name if is_current else current_names.get(user.pk, "未设置")})
    data.update(stage="confirm", role=role, is_current=is_current)
    return {"token": signing.dumps(data, salt=SALT, compress=True), "rows": rows,
            "role_label": TrainingCycleMember.Role(role).label, "return_query": data["return_query"]}


@transaction.atomic
def confirm_member_add(*, actor, cycle, token):
    # 与单人成员写入采用相同的用户锁顺序，随后重新校验预览现状。
    data, _users = load_member_add(actor=actor, cycle=cycle, token=token, stage="confirm")
    list(User.objects.select_for_update().filter(pk__in=data["ids"]).order_by("pk"))
    cycle = TrainingCycle.objects.select_for_update().get(pk=cycle.pk)
    data, users = load_member_add(actor=actor, cycle=cycle, token=token, stage="confirm")
    _require_permissions(actor, is_current=data["is_current"])
    for user in users:
        save_cycle_member(TrainingCycleMember(training_cycle=cycle, user=user,
                                             role=data["role"], is_current=data["is_current"]))
    return data["return_query"]
