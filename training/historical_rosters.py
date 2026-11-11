"""已确认的历史应交选手名单及撤销记录。"""

from datetime import date

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.services.users import annotate_identity_labels, get_user_display_name, require_distinguishable_users

from .models import TrainingCycle, TrainingCycleMember, TrainingPlan
from .plan_members import require_manager
from .scheduling import audit
from .selectors import _daily_competitors, training_log_stat_slots

CONFIRMED = "确认历史应交选手名单"
REVOKED = "撤销历史应交选手名单"
SALT = "training.historical-roster"
User = get_user_model()


def roster_history(plan):
    records = list(plan.change_records.filter(action__in=(CONFIRMED, REVOKED)).select_related("actor"))
    revoked = {record.after["record_id"]: record for record in records if record.action == REVOKED}
    return [(record, revoked.get(record.pk)) for record in records if record.action == CONFIRMED]


def confirmed_rosters(plan):
    records = list(plan.change_records.filter(action__in=(CONFIRMED, REVOKED)).values_list("pk", "action", "after"))
    revoked = {payload["record_id"] for _, action, payload in records if action == REVOKED}
    return {
        date.fromisoformat(day): set(payload["user_ids"])
        for pk, action, payload in records if action == CONFIRMED and pk not in revoked
        for day in payload["dates"]
    }


def historical_candidates(plan):
    return User.objects.filter(
        Q(training_cycle_memberships__training_cycle_id=plan.training_cycle_id,
          training_cycle_memberships__role=TrainingCycleMember.Role.COMPETITOR)
        | Q(training_plan_participations__training_plan__training_cycle_id=plan.training_cycle_id)
    ).distinct()


def _snapshot(plan, start, end, ids, reason):
    if not plan.published_at or not plan.schedule_published_at:
        raise ValidationError("计划和排班均发布后才能补录历史名单。")
    if not plan.start_date <= start <= end <= plan.end_date or end >= timezone.localdate():
        raise ValidationError("日期区间须在计划范围内，且早于今天。")
    if not reason.strip():
        raise ValidationError("请填写名单依据。")
    candidates = historical_candidates(plan)
    users = list(annotate_identity_labels(candidates).filter(pk__in=ids).order_by("pk"))
    if {user.pk for user in users} != set(ids):
        raise ValidationError("部分人员已不属于该周期的选手范围，请重新选择。")
    if ids:
        require_distinguishable_users(candidates, ids)
    dates = sorted(set(training_log_stat_slots(plan, start, end).values_list("day__date", flat=True)))
    unresolved = [day for day, (_, complete) in _daily_competitors(
        plan, dates, include_backfill=False,
    ).items() if not complete]
    if not unresolved:
        raise ValidationError("该区间没有需要补录名单的训练日。")
    if set(unresolved).intersection(confirmed_rosters(plan)):
        raise ValidationError("该区间包含已补录的训练日，请调整日期或先撤销原补录。")
    return {
        "start": start.isoformat(), "end": end.isoformat(), "dates": [day.isoformat() for day in unresolved],
        "user_ids": [user.pk for user in users], "names": [get_user_display_name(user) for user in users],
        "revision": plan.change_records.filter(action__in=(CONFIRMED, REVOKED))
        .order_by("-pk").values_list("pk", flat=True).first(),
    }


def preview_roster(actor, plan, *, start, end, ids, reason):
    require_manager(actor, plan)
    snapshot = _snapshot(plan, start, end, ids, reason)
    token = signing.dumps(
        {"actor": actor.pk, "plan": plan.pk, "snapshot": snapshot, "reason": reason}, salt=SALT, compress=True,
    )
    return snapshot, token


@transaction.atomic
def confirm_roster(actor, plan, token):
    try:
        data = signing.loads(token, salt=SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError("预览已过期或无效，请重新预览。") from exc
    if data["actor"] != actor.pk or data["plan"] != plan.pk:
        raise ValidationError("预览与当前操作不符，请重新预览。")
    snapshot = data["snapshot"]
    ids = snapshot["user_ids"]
    list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    TrainingCycle.objects.select_for_update().get(pk=plan.training_cycle_id)
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    actor = require_manager(actor, plan)
    current = _snapshot(plan, date.fromisoformat(snapshot["start"]), date.fromisoformat(snapshot["end"]),
                        ids, data["reason"])
    if current != snapshot:
        raise ValidationError("训练日或名单已变化，请重新预览。")
    audit(plan, actor, CONFIRMED, after=snapshot, reason=data["reason"])


@transaction.atomic
def revoke_roster(actor, plan, record_id, reason):
    plan = TrainingPlan.objects.select_for_update().get(pk=plan.pk)
    actor = require_manager(actor, plan)
    if not reason.strip():
        raise ValidationError("请填写撤销原因。")
    if not any(record.pk == record_id and revoked is None for record, revoked in roster_history(plan)):
        raise ValidationError("该补录记录不存在或已撤销。")
    audit(plan, actor, REVOKED, after={"record_id": record_id}, reason=reason)
