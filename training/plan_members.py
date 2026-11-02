"""计划参与选手的固定名单预览及事务写入。"""

from django import forms
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.services.user_management import normalize_ids
from accounts.services.users import get_user_display_name
from core.utils.forms import StyledFormMixin

from .models import TrainingCycle, TrainingCycleMember, TrainingPlan, TrainingPlanParticipant
from .scheduling import audit, plan_manager, visible_plans

SALT = "training.plan-members"
User = get_user_model()


class PlanMemberActionForm(StyledFormMixin, forms.Form):
    operation = forms.ChoiceField(
        label="操作", choices=[("", "请选择操作"), ("add", "添加计划成员")],
        widget=forms.Select(attrs={"data-bulk-operation": ""}),
    )


def require_manager(actor, plan):
    actor = User.objects.get(pk=actor.pk)
    if not actor.is_active or not visible_plans(actor).filter(pk=plan.pk).exists() or not plan_manager(actor, plan):
        raise PermissionDenied
    return actor


def candidates(plan):
    return User.objects.filter(
        is_active=True, training_cycle_memberships__training_cycle_id=plan.training_cycle_id,
        training_cycle_memberships__role=TrainingCycleMember.Role.COMPETITOR,
        training_cycle_memberships__is_current=True,
    ).exclude(training_plan_participations__in=plan.participants.filter(is_active=True))


def _state(plan, ids, operation):
    users = list(User.objects.filter(pk__in=ids).order_by("pk"))
    participants = list(plan.participants.filter(user_id__in=ids).order_by("user_id"))
    if len(users) != len(ids):
        raise ValidationError("部分用户已不存在，请重新选择。")
    if operation == "add":
        if set(candidates(plan).filter(pk__in=ids).values_list("pk", flat=True)) != set(ids):
            raise ValidationError("仅可添加所属周期中账号有效、当前在训且尚未参与本计划的选手。")
    elif operation == "remove":
        if len(ids) != 1 or len(participants) != 1 or not participants[0].is_active:
            raise ValidationError("成员已退出或不属于本计划，请重新选择。")
    else:
        raise ValidationError("成员操作无效。")
    state = {
        "plan": [plan.training_cycle_id, plan.title],
        "users": [[u.pk, u.username, u.last_name, u.first_name, u.is_active] for u in users],
        "participants": [[p.pk, p.user_id, p.is_active, p.updated_at.isoformat()] for p in participants],
    }
    return users, state


def preview_members(*, actor, plan, ids, operation, return_query=""):
    plan = TrainingPlan.objects.get(pk=plan.pk)
    require_manager(actor, plan)
    ids = normalize_ids(ids)
    users, state = _state(plan, ids, operation)
    token = signing.dumps({
        "actor": actor.pk, "plan": plan.pk, "ids": ids, "operation": operation,
        "state": state, "return_query": return_query,
    }, salt=SALT, compress=True)
    return {
        "token": token, "operation": operation, "return_query": return_query,
        "rows": [{"name": get_user_display_name(u), "username": u.username} for u in users],
    }


@transaction.atomic
def confirm_members(*, actor, plan, token):
    try:
        data = signing.loads(token, salt=SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError("操作已过期或无效，请返回列表重新预览。") from exc
    if data["actor"] != actor.pk or data["plan"] != plan.pk:
        raise ValidationError("操作名单与当前页面不符，请重新预览。")
    # 与周期成员维护保持用户、周期的锁顺序，再锁计划串行化成员变更。
    list(User.objects.select_for_update().filter(pk__in=data["ids"]).order_by("pk"))
    TrainingCycle.objects.select_for_update().get(pk=plan.training_cycle_id)
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    actor = require_manager(actor, plan)
    _users, state = _state(plan, data["ids"], data["operation"])
    if state != data["state"]:
        raise ValidationError("计划或所选成员状态已变化，请返回列表重新预览。")
    before = {"参与选手": sorted(plan.participants.filter(is_active=True).values_list("user_id", flat=True))}
    for user_id in data["ids"]:
        if data["operation"] == "add":
            participant, created = TrainingPlanParticipant.objects.get_or_create(training_plan=plan, user_id=user_id)
            if not created:
                participant.is_active = True
                participant.save(update_fields=["is_active", "updated_at"])
        else:
            participant = plan.participants.get(user_id=user_id)
            participant.is_active = False
            participant.save(update_fields=["is_active", "updated_at"])
    audit(plan, actor, "添加计划成员" if data["operation"] == "add" else "退出计划成员", before=before,
          after={"参与选手": sorted(plan.participants.filter(is_active=True).values_list("user_id", flat=True))})
    return data["return_query"]
