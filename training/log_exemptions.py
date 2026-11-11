"""训练日志免交规则及其变更记录。"""

import json
from datetime import date, timedelta
from hashlib import sha256

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from accounts.services.users import annotate_identity_labels, get_user_display_name, require_distinguishable_users

from .models import TrainingPlan
from .scheduling import audit

ACTIONS = {"add": "新增日志免交", "replace": "替换日志免交", "end": "结束日志免交"}
ROLES = {"coach": "负责教练", "competitor": "参与选手"}
SALT = "training.log-exemptions.multiple"
User = get_user_model()


def require_admin(actor):
    if not (actor.is_active and actor.is_superuser):
        raise PermissionDenied


def exemption_candidates(plan, role=None):
    coaches = Q(pk__in=plan.responsible_coaches.values("pk"))
    competitors = Q(pk__in=plan.participants.filter(is_active=True).values("user_id"))
    return User.objects.filter({"coach": coaches, "competitor": competitors}.get(role, coaches | competitors))


def exemption_history(plan):
    return plan.change_records.filter(action__in=ACTIONS.values()).select_related("actor").order_by("pk")


def _apply(rules, key, change):
    if (target := change["target"]) is not None:
        previous = rules.pop(target)
        if previous["start"] < change["start"]:
            rules[target] = {
                **previous,
                "end": (date.fromisoformat(change["start"]) - timedelta(days=1)).isoformat(),
            }
    if change["rule"] is not None:
        rules[key] = change["rule"]


def exemption_rules(history):
    rules = {}
    for record in history:
        _apply(rules, record.pk, record.after)
    return rules


def exempt_users(rules, dates):
    return {
        day: {
            pk for rule in rules.values()
            if rule["start"] <= day.isoformat() <= rule["end"]
            for pk in rule["user_ids"]
        }
        for day in dates
    }


def _preview(plan, params):
    from .selectors import training_log_daily_rosters

    start = date.fromisoformat(params["start"])
    end = date.fromisoformat(params["end"]) if params["end"] else plan.end_date
    operation = params["operation"]
    target = params["target"]
    roles, user_ids = params["roles"], set(params["user_ids"])
    if not params["reason"].strip() or len(params["reason"]) > 2000:
        raise ValidationError("请填写原因，最多 2000 字。")
    if not plan.start_date <= start <= end <= plan.end_date:
        raise ValidationError("生效日期须在计划范围内，且结束日期不能早于开始日期。")
    if operation not in ACTIONS or (target is None) != (operation == "add"):
        raise ValidationError("请选择有效的操作和规则。")

    history = list(exemption_history(plan))
    rules = exemption_rules(history)
    previous = rules.get(target)
    if target is not None and (previous is None or not previous["start"] <= start.isoformat() <= previous["end"]):
        raise ValidationError("生效日期须在所选规则当前有效的日期内。")

    rule = None
    if operation == "end":
        if roles or user_ids or params["end"]:
            raise ValidationError("结束规则只需指定生效日期和原因。")
    else:
        if not (roles or user_ids) or set(roles) - ROLES.keys():
            raise ValidationError("请至少勾选一个免交角色或指定一名人员。")
        users = exemption_candidates(plan)
        if set(users.filter(pk__in=user_ids).values_list("pk", flat=True)) != user_ids:
            raise ValidationError("所选人员已不在计划的负责教练或参与选手名单中，请重新选择。")
        require_distinguishable_users(users, user_ids)
        role_user_ids = {
            role: sorted(exemption_candidates(plan, role).values_list("pk", flat=True)) for role in roles
        }
        grouped_ids = {pk for ids in role_user_ids.values() for pk in ids}
        members = list(annotate_identity_labels(users).filter(pk__in=grouped_ids | user_ids).order_by("pk"))
        if not members:
            raise ValidationError("所选角色没有可免交的成员，请重新选择。")
        role_names = [f"全部{ROLES[role]}" for role in roles]
        labels = role_names + (["指定人员"] if user_ids else [])
        rule = {
            "start": start.isoformat(), "end": end.isoformat(), "label": "、".join(labels),
            "role_names": role_names, "role_user_ids": role_user_ids,
            "specified_ids": sorted(user_ids),
            "specified_names": [get_user_display_name(user) for user in members if user.pk in user_ids],
            "user_ids": [user.pk for user in members],
            "names": [get_user_display_name(user) for user in members],
        }

    change = {"target": target, "start": start.isoformat(), "rule": rule}
    last_day = max(end if rule else start, date.fromisoformat(previous["end"]) if previous else start)
    # 预览未来训练日时，使用当前排班及当前可核定的选手名单。
    coaches, competitors = training_log_daily_rosters(plan, start, min(last_day, plan.end_date))
    before = exempt_users(rules, coaches)
    _apply(rules, None, change)
    after = exempt_users(rules, coaches)
    rows = []
    affected = set()
    for day, daily_coaches in coaches.items():
        daily_competitors, _ = competitors[day]
        added = after[day] - before[day]
        removed = before[day] - after[day]
        for role, roster in (("选手", daily_competitors), ("负责教练", daily_coaches)):
            for pk in sorted(roster & (added | removed)):
                rows.append({"date": day.isoformat(), "role": role, "user_id": pk, "delta": -1 if pk in added else 1})
                affected.add(pk)
    names = {
        user.pk: get_user_display_name(user)
        for user in annotate_identity_labels(User.objects.all()).filter(pk__in=affected)
    } if affected else {}
    for row in rows:
        row["name"] = names[row["user_id"]]
    return {
        "revision": history[-1].pk if history else None, "change": change, "previous": previous,
        "rows": rows, "delta": sum(row["delta"] for row in rows),
    }


def _digest(snapshot):
    return sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def preview_exemption(actor, plan, params):
    require_admin(actor)
    snapshot = _preview(plan, params)
    token = signing.dumps(
        {"actor": actor.pk, "plan": plan.pk, "params": params, "digest": _digest(snapshot)}, salt=SALT, compress=True,
    )
    return snapshot, token


@transaction.atomic
def confirm_exemption(actor, plan, token):
    require_admin(actor)
    try:
        payload = signing.loads(token, salt=SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError("预览已过期或无效，请重新预览。") from exc
    if payload["actor"] != actor.pk or payload["plan"] != plan.pk:
        raise ValidationError("预览与当前操作不符，请重新预览。")
    params = payload["params"]
    plan = TrainingPlan.objects.select_for_update().filter(pk=plan.pk).first()
    if plan is None:
        raise ValidationError("训练计划已不存在。")
    snapshot = _preview(plan, params)
    if _digest(snapshot) != payload["digest"]:
        raise ValidationError("免交规则、排班或人员名单已变化，请重新预览。")
    audit(
        plan, actor, ACTIONS[params["operation"]], before=snapshot["previous"],
        after=snapshot["change"], reason=params["reason"],
    )
