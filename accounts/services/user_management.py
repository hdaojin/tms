"""前端账号管理：固定目标预览、现状校验与原子写入。"""

import hashlib
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import CharField, Q
from django.db.models.functions import Concat

from accounts.models import GroupProfile, UserProfile
from accounts.selectors import permission_display_name
from accounts.services.roles import _user_roles_state
from accounts.services.users import get_user_display_name
from accounts.user_management_forms import UserManagementForm

User = get_user_model()
SALT = "accounts.user-management"
PARAMETER_SALT = "accounts.user-management-parameters"
PARAMETER_OPERATIONS = {"add_roles", "remove_roles", "set_leave_date"}


def prepare_user_action(*, actor, ids, operation, return_query=""):
    """在进入参数页时固定目标，后续不再重新解析筛选结果。"""
    require_manager(actor)
    if operation not in PARAMETER_OPERATIONS:
        raise ValidationError("此操作不需要填写额外参数。")
    ids = normalize_ids(ids)
    users = _users(ids)
    protected = [get_user_display_name(user) for user in users if user.is_superuser]
    if operation in ("add_roles", "remove_roles") and protected:
        raise ValidationError(f"{'、'.join(protected)}：超级管理员账号受保护，不能执行此操作。")
    token = signing.dumps(
        {"actor": actor.pk, "ids": ids, "operation": operation, "return_query": return_query},
        salt=PARAMETER_SALT,
        compress=True,
    )
    return {"token": token, "users": users, "operation": operation, "return_query": return_query}


def load_user_action(*, actor, token):
    require_manager(actor)
    try:
        data = signing.loads(token, salt=PARAMETER_SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError("操作名单已失效，请返回列表重新选择。") from exc
    if data["actor"] != actor.pk:
        raise ValidationError("操作所属管理员已变化，请重新选择。")
    return {**data, "token": token, "users": _users(data["ids"])}


def filter_users(queryset, filters):
    query = filters.get("q", "")
    if query:
        queryset = queryset.alias(full_name=Concat("last_name", "first_name", output_field=CharField()))
        queryset = queryset.filter(
            Q(username__icontains=query) | Q(full_name__icontains=query) | Q(profile__student_id__icontains=query)
        )
    if filters.get("active"):
        queryset = queryset.filter(is_active=filters["active"] == "1")
    role = filters.get("role")
    if role == "none":
        queryset = queryset.filter(groups__isnull=True)
    elif role:
        queryset = queryset.filter(groups__pk=role)
    return queryset.distinct()


def require_manager(actor):
    # 不信任调用方缓存的 User 标志，确认时再次检查数据库状态。
    if not User.objects.filter(pk=actor.pk, is_active=True, is_superuser=True).exists():
        raise PermissionDenied


def normalize_ids(values):
    try:
        ids = sorted({int(value) for value in values})
    except (TypeError, ValueError) as exc:
        raise ValidationError("所选用户编号无效。") from exc
    if not ids or ids[0] <= 0:
        raise ValidationError("请至少选择一位用户。")
    return ids


def _users(ids):
    users = list(
        User.objects.filter(pk__in=ids)
        .select_related("profile")
        .prefetch_related("groups", "user_permissions")
        .order_by("pk")
    )
    if len(users) != len(ids):
        raise ValidationError("部分用户已不存在，请重新选择并预览。")
    return users


def _state(users, payload):
    operation = payload["operation"]
    rows = []
    role_ids = set(payload["roles"])
    for user in users:
        profile = getattr(user, "profile", None)
        row = {
            "id": user.pk,
            "username": user.username,
            "name": get_user_display_name(user),
            "active": user.is_active,
            "superuser": user.is_superuser,
        }
        if operation in ("add_roles", "remove_roles"):
            row["groups"] = sorted(group.pk for group in user.groups.all())
            row["direct"] = sorted(permission.pk for permission in user.user_permissions.all())
            role_ids.update(row["groups"])
        if operation in ("set_leave_date", "clear_leave_date"):
            row["profile"] = profile.pk if profile else None
            row["join_date"] = str(profile.join_date) if profile and profile.join_date else None
            row["leave_date"] = str(profile.leave_date) if profile and profile.leave_date else None
        rows.append(row)
    roles = _user_roles_state(users[0], role_ids)["roles"] if operation in ("add_roles", "remove_roles") else []
    return {"users": rows, "roles": roles}


def _digest(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _validate_payload(payload):
    form = UserManagementForm(
        {
            "operation": payload.get("operation"),
            "roles": payload.get("roles", []),
            "leave_date": payload.get("leave_date"),
        }
    )
    if not form.is_valid():
        raise ValidationError([message for errors in form.errors.values() for message in errors])
    return form.payload()


def _changes(users, payload):
    operation = payload["operation"]
    role_names = dict(Group.objects.filter(pk__in=payload["roles"]).values_list("pk", "name"))
    rows, errors = [], []
    for user in users:
        name = f"{get_user_display_name(user)}（{user.username}）"
        if user.is_superuser and operation in ("deactivate", "add_roles", "remove_roles"):
            errors.append(f"{name}：超级管理员账号受保护，不能执行此操作。")
            continue
        profile = getattr(user, "profile", None)
        if operation in ("activate", "deactivate"):
            before = "已激活" if user.is_active else "未激活"
            after = "已激活" if operation == "activate" else "未激活"
        elif operation in ("add_roles", "remove_roles"):
            current = {group.pk: group.name for group in user.groups.all()}
            after_ids = set(current) | set(role_names) if operation == "add_roles" else set(current) - set(role_names)
            before = "、".join(current[pk] for pk in sorted(current)) or "无"
            names = current | role_names
            after = "、".join(names[pk] for pk in sorted(after_ids)) or "无"
        else:
            before = profile.leave_date.isoformat() if profile and profile.leave_date else "未填写"
            after = payload["leave_date"] or "未填写"
            if (
                payload["leave_date"]
                and profile
                and profile.join_date
                and date.fromisoformat(payload["leave_date"]) < profile.join_date
            ):
                errors.append(f"{name}：离开日期不能早于入读日期（{profile.join_date}）。")
        rows.append(
            {
                "name": get_user_display_name(user),
                "username": user.username,
                "before": before,
                "after": after,
                "changed": before != after,
            }
        )
    if errors:
        raise ValidationError(errors)
    return rows


def preview_users(*, actor, ids, payload):
    require_manager(actor)
    ids = normalize_ids(ids)
    payload = _validate_payload(payload)
    users = _users(ids)
    rows = _changes(users, payload)
    state = _state(users, payload)
    role_operation = payload["operation"] in ("add_roles", "remove_roles")
    if role_operation:
        permissions = {role["pk"]: set(role["permissions"]) for role in state["roles"]}
        differences = set()
        for row, user_state in zip(rows, state["users"], strict=True):
            current, selected = set(user_state["groups"]), set(payload["roles"])
            after_roles = current | selected if payload["operation"] == "add_roles" else current - selected
            before = set(user_state["direct"]).union(*(permissions[pk] for pk in current))
            after = set(user_state["direct"]).union(*(permissions[pk] for pk in after_roles))
            row["granted"], row["revoked"] = sorted(after - before), sorted(before - after)
            differences.update(before ^ after)
        labels = {
            permission.pk: permission_display_name(permission)
            for permission in Permission.objects.filter(pk__in=differences).select_related("content_type")
        }
        for row in rows:
            row["granted"] = [labels[pk] for pk in row["granted"]]
            row["revoked"] = [labels[pk] for pk in row["revoked"]]
    token = signing.dumps(
        {"actor": actor.pk, "ids": ids, "payload": payload, "digest": _digest(state)}, salt=SALT, compress=True
    )
    return {
        "token": token,
        "rows": rows,
        "count": len(rows),
        "unchanged": sum(not row["changed"] for row in rows),
        "operation": dict(UserManagementForm.base_fields["operation"].choices)[payload["operation"]],
        "role_operation": role_operation,
    }


@transaction.atomic
def save_users(*, actor, token, target_id=None):
    require_manager(actor)
    try:
        preview = signing.loads(token, salt=SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError("预览已失效，请重新预览。") from exc
    if preview["actor"] != actor.pk:
        raise ValidationError("预览所属管理员已变化，请重新预览。")
    ids, payload = preview["ids"], preview["payload"]
    if target_id is not None and (ids != [target_id] or payload["operation"] in ("add_roles", "remove_roles")):
        raise ValidationError("预览与当前用户管理页面不一致，请重新预览。")
    role_ids = set(payload["roles"])
    if payload["operation"] in ("add_roles", "remove_roles"):
        role_ids.update(Group.objects.filter(user__pk__in=ids).values_list("pk", flat=True))
        list(Group.objects.select_for_update().filter(pk__in=role_ids).order_by("pk"))
        list(GroupProfile.objects.select_for_update().filter(group_id__in=role_ids).order_by("group_id"))
    list(User.objects.select_for_update().filter(pk__in=set(ids) | {actor.pk}).order_by("pk"))
    list(UserProfile.objects.select_for_update().filter(user_id__in=ids).order_by("user_id"))
    require_manager(actor)
    payload = _validate_payload(payload)
    users = _users(ids)
    if preview["digest"] != _digest(_state(users, payload)):
        raise ValidationError("用户状态、日期或角色授权在预览后发生变化，请重新预览。")
    rows = _changes(users, payload)
    for user, row in zip(users, rows, strict=True):
        if not row["changed"]:
            continue
        operation = payload["operation"]
        if operation in ("activate", "deactivate"):
            user.is_active = operation == "activate"
            user.save(update_fields=["is_active"])
        elif operation == "add_roles":
            user.groups.add(*payload["roles"])
        elif operation == "remove_roles":
            user.groups.remove(*payload["roles"])
        else:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.leave_date = date.fromisoformat(payload["leave_date"]) if payload["leave_date"] else None
            profile.save(update_fields=["leave_date"])
    return {"count": len(rows), "changed": sum(row["changed"] for row in rows)}
