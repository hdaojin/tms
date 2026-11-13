"""训练计划三类人员名单及其事务写入。"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.services.user_management import normalize_ids
from accounts.services.users import get_user_display_name, require_distinguishable_users
from core.utils.forms import StyledFormMixin

from .models import TrainingCycle, TrainingCycleMember, TrainingPlan, TrainingPlanDutyOrder, TrainingPlanParticipant
from .plan_people import PlanStaffSelect, eligible_staff
from .scheduling import audit, check_roster_removal, plan_manager, visible_plans

ROSTER_LABELS = {"responsible_coaches": "负责教练", "duty_personnel": "值班人员"}

SALT = "training.plan-members"
User = get_user_model()


class PlanMemberActionForm(StyledFormMixin, forms.Form):
    operation = forms.ChoiceField(
        label="操作", choices=[("", "请选择操作"), ("add", "添加计划成员")],
        widget=forms.Select(attrs={"data-bulk-operation": ""}),
    )


class ParticipantGroupsForm(StyledFormMixin, forms.Form):
    elite_class = forms.BooleanField(
        label="精英班（本周期全体选手）", required=False, initial=True,
        widget=forms.CheckboxInput(attrs={"data-bulk-extra-selection": ""}),
    )
    groups = forms.ModelMultipleChoiceField(
        label="用户角色", queryset=Group.objects.order_by("name"), required=False,
        widget=forms.SelectMultiple(attrs={"data-bulk-extra-selection": ""}),
    )

    def selected_ids(self, plan):
        eligible = candidates(plan)
        if not self.cleaned_data["elite_class"]:
            eligible = eligible.filter(groups__in=self.cleaned_data["groups"])
        return set(eligible.values_list("pk", flat=True))


class PlanRosterForm(StyledFormMixin, forms.Form):
    def __init__(self, *args, plan, role, **kwargs):
        super().__init__(*args, **kwargs)
        widget = PlanStaffSelect()
        widget.plan_id = plan.pk
        members = list(getattr(plan, role).all())
        self.fields[role] = forms.ModelMultipleChoiceField(
            label=ROSTER_LABELS[role], queryset=User.objects.all(), required=False,
            widget=widget, initial=members,
        )
        field = self[role]
        ids = [str(pk) for pk in (field.value() or []) if str(pk).isdecimal()]
        widget.selected = [
            {"id": user.pk, "label": get_user_display_name(user)}
            for user in User.objects.filter(pk__in=ids).order_by("last_name", "first_name", "pk")
        ]


@transaction.atomic
def save_roster(actor, plan, role, selected):
    if role not in ROSTER_LABELS:
        raise PermissionDenied
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    actor = require_manager(actor, plan)
    roster = getattr(plan, role)
    before = set(roster.values_list("pk", flat=True))
    added = selected - before
    if set(eligible_staff(role, plan).filter(pk__in=added).values_list("pk", flat=True)) != added:
        raise ValidationError("新指定的人员必须账号有效且符合该职责的候选条件。")
    if added:
        visible = User.objects.filter(pk__in=eligible_staff(role, plan).values("pk") | roster.values("pk"))
        require_distinguishable_users(visible, added)
    check_roster_removal(plan, role, before - selected)
    label = ROSTER_LABELS[role]
    if plan.published_at and before and not selected:
        raise ValidationError(f"已发布计划至少保留一名{label}。")
    if selected != before:
        roster.set(selected)
        if role == "duty_personnel":
            TrainingPlanDutyOrder.objects.filter(training_plan=plan, user_id__in=before - selected).delete()
            max_order = max(TrainingPlanDutyOrder.objects.filter(training_plan=plan).values_list("order", flat=True), default=0)
            TrainingPlanDutyOrder.objects.bulk_create([
                TrainingPlanDutyOrder(training_plan=plan, user_id=user_id, order=max_order + index)
                for index, user_id in enumerate(sorted(added), 1)
            ], ignore_conflicts=True)
        TrainingPlan.objects.filter(pk=plan.pk).update(updated_at=timezone.now())
        audit(plan, actor, f"维护{label}", before={label: sorted(before)}, after={label: sorted(selected)})


@transaction.atomic
def change_coaches(*, actor, plan, ids, operation):
    ids = normalize_ids(ids)
    list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    TrainingCycle.objects.select_for_update().get(pk=plan.training_cycle_id)
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    require_manager(actor, plan)
    current = set(plan.responsible_coaches.values_list("pk", flat=True))
    selected = set(ids)
    if operation == "add":
        if current & selected or set(eligible_staff("responsible_coaches", plan).filter(
            pk__in=selected
        ).values_list("pk", flat=True)) != selected:
            raise ValidationError("所选教练已加入或不再符合候选条件，请重新选择。")
        updated = current | selected
    elif operation == "remove" and len(selected) == 1 and selected <= current:
        updated = current - selected
    else:
        raise ValidationError("所选教练不在计划名单中，请重新选择。")
    save_roster(actor, plan, "responsible_coaches", updated)


def ordered_duty(plan):
    from django.db.models import IntegerField, OuterRef, Subquery, Value
    from django.db.models.functions import Coalesce

    orders = TrainingPlanDutyOrder.objects.filter(training_plan=plan, user_id=OuterRef("pk"))
    return plan.duty_personnel.annotate(
        duty_order=Coalesce(Subquery(orders.values("order")[:1]), Value(0), output_field=IntegerField())
    ).order_by("duty_order", "last_name", "first_name", "pk")


@transaction.atomic
def change_duty(*, actor, plan, operation, orders):
    ids = normalize_ids(orders)
    try:
        values = {int(pk): int(value) for pk, value in orders.items()}
    except (TypeError, ValueError) as exc:
        raise ValidationError("排序号必须是非负整数。") from exc
    if any(value < 0 or value > 2147483647 for value in values.values()):
        raise ValidationError("排序号必须是非负整数。")
    list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    TrainingCycle.objects.select_for_update().get(pk=plan.training_cycle_id)
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    require_manager(actor, plan)
    current = set(plan.duty_personnel.values_list("pk", flat=True))
    selected = set(ids)
    before = list(TrainingPlanDutyOrder.objects.filter(training_plan=plan).order_by("user_id").values_list("user_id", "order"))
    if operation == "add":
        eligible = set(eligible_staff("duty_personnel", plan).filter(pk__in=ids).values_list("pk", flat=True))
        if selected & current or selected != eligible:
            raise ValidationError("所选值班人员已加入或不再符合候选条件，请重新选择。")
        save_roster(actor, plan, "duty_personnel", current | selected)
    elif operation == "remove" and len(selected) == 1 and selected <= current:
        save_roster(actor, plan, "duty_personnel", current - selected)
        TrainingPlanDutyOrder.objects.filter(training_plan=plan, user_id__in=ids).delete()
        after = list(TrainingPlanDutyOrder.objects.filter(training_plan=plan).order_by("user_id").values_list("user_id", "order"))
        if before != after:
            audit(plan, actor, "调整值班顺序", before={"值班顺序": before}, after={"值班顺序": after})
        return
    elif operation != "order" or selected != current:
        raise ValidationError("值班名单已变化，请刷新后重新操作。")
    for pk, order in values.items():
        TrainingPlanDutyOrder.objects.update_or_create(training_plan=plan, user_id=pk, defaults={"order": order})
    after = list(TrainingPlanDutyOrder.objects.filter(training_plan=plan).order_by("user_id").values_list("user_id", "order"))
    if before != after:
        TrainingPlan.objects.filter(pk=plan.pk).update(updated_at=timezone.now())
        audit(plan, actor, "调整值班顺序", before={"值班顺序": before}, after={"值班顺序": after})


def require_manager(actor, plan):
    actor = User.objects.get(pk=actor.pk)
    if not actor.is_active or not visible_plans(actor).filter(pk=plan.pk).exists() or not plan_manager(actor, plan):
        raise PermissionDenied
    return actor


def candidates(plan):
    return User.objects.filter(
        is_active=True, training_cycle_memberships__training_cycle_id=plan.training_cycle_id,
        training_cycle_memberships__role=TrainingCycleMember.Role.COMPETITOR,
    ).exclude(training_plan_participations__in=plan.participants.filter(is_active=True))


def _state(plan, ids, operation):
    users = list(User.objects.filter(pk__in=ids).select_related("profile").order_by("pk"))
    participants = list(plan.participants.filter(user_id__in=ids).order_by("user_id"))
    if len(users) != len(ids):
        raise ValidationError("部分用户已不存在，请重新选择。")
    if operation == "add":
        if set(candidates(plan).filter(pk__in=ids).values_list("pk", flat=True)) != set(ids):
            raise ValidationError("仅可添加所属周期中账号有效且尚未参与本计划的选手。")
        eligible = User.objects.filter(training_cycle_memberships__training_cycle_id=plan.training_cycle_id,
                                       training_cycle_memberships__role=TrainingCycleMember.Role.COMPETITOR)
        require_distinguishable_users(eligible, ids)
    elif operation == "remove":
        if len(ids) != 1 or len(participants) != 1 or not participants[0].is_active:
            raise ValidationError("成员已退出或不属于本计划，请重新选择。")
        check_roster_removal(plan, "participants", set(ids))
        if plan.published_at and plan.participants.filter(is_active=True).count() <= 1:
            raise ValidationError("已发布计划至少保留一名参与选手。")
    else:
        raise ValidationError("成员操作无效。")
    state = {
        "plan": [plan.training_cycle_id, plan.title],
        "users": [[u.pk, u.last_name, u.first_name, u.is_active] for u in users],
        "participants": [[p.pk, p.user_id, p.is_active, p.updated_at.isoformat()] for p in participants],
    }
    return users, state


def preview_members(*, actor, plan, ids, operation, return_query="", audience=""):
    plan = TrainingPlan.objects.get(pk=plan.pk)
    require_manager(actor, plan)
    ids = normalize_ids(ids)
    users, state = _state(plan, ids, operation)
    token = signing.dumps({
        "actor": actor.pk, "plan": plan.pk, "ids": ids, "operation": operation,
        "state": state, "return_query": return_query,
        "audience": audience, "previous_audience": plan.implementation_audience,
    }, salt=SALT, compress=True)
    return {
        "token": token, "operation": operation, "return_query": return_query, "audience": audience,
        "rows": [{"name": get_user_display_name(u), "note": getattr(getattr(u, "profile", None), "name_disambiguation", "")}
                 for u in users],
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
    after = {}
    if data.get("audience"):
        if data["previous_audience"] != plan.implementation_audience:
            raise ValidationError("计划实施对象已变化，请重新预览。")
        before["实施对象"] = plan.implementation_audience
        plan.implementation_audience = data["audience"]
        plan.save(update_fields=["implementation_audience", "updated_at"])
        after["实施对象"] = plan.implementation_audience
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
    after["参与选手"] = sorted(plan.participants.filter(is_active=True).values_list("user_id", flat=True))
    audit(plan, actor, "添加计划成员" if data["operation"] == "add" else "退出计划成员", before=before, after=after)
    return data["return_query"]
