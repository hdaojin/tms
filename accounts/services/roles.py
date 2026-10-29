from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.models import GroupProfile
from accounts.selectors import permission_display_name
from accounts.services.groups import ensure_group_profile
from accounts.services.permission_assignments import sync_group_permission_assignments
from accounts.services.users import get_user_display_name
from core.permissions import get_permission_bundle_spec_map
from standards.models import TechnicalDomain, TechnicalDomainGroupScope


def role_state(group):
    if group is None:
        return None
    profile = GroupProfile.objects.filter(group=group).first()
    return {
        "pk": group.pk,
        "name": group.name,
        "description": (profile.description or "") if profile else "",
        "bundles": sorted(profile.selected_permission_bundles) if profile else [],
        "explicit_permissions": sorted(profile.explicit_permissions.values_list("pk", flat=True)) if profile else [],
        "domains": sorted(group.technical_domain_scopes.values_list("technical_domain_id", flat=True)),
        "members": sorted(group.user_set.values_list("pk", flat=True)),
        "projection": sorted(group.permissions.values_list("pk", flat=True)),
        "codename": profile.codename if profile else None,
    }


def role_initial(group, *, copying=False):
    state = role_state(group)
    if not state:
        return {}
    return {
        "name": f"{state['name']}（副本）" if copying else state["name"],
        "description": state["description"],
        "bundles": state["bundles"],
        "explicit_permissions": state["explicit_permissions"],
        "members": [] if copying else state["members"],
        "domains": [] if copying else state["domains"],
    }


def preview_role(*, actor, group, payload):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    state = role_state(group)
    token = signing.dumps({"state": state, "payload": payload}, salt="accounts.role-preview", compress=True)
    before = state or {
        "members": [],
        "domains": [],
        "bundles": [],
        "explicit_permissions": [],
        "name": "",
        "description": "",
    }
    changes = [
        {"label": label, "before": before[key], "after": payload[key]}
        for key, label in (
            ("name", "角色名称"),
            ("description", "职责说明"),
            ("bundles", "业务权限包"),
            ("domains", "技术领域编号"),
            ("members", "成员编号"),
            ("explicit_permissions", "额外权限编号"),
        )
        if before[key] != payload[key]
    ]
    specs = get_permission_bundle_spec_map()
    display_maps = {
        "业务权限包": {code: spec.name for code, spec in specs.items()},
        "技术领域编号": {
            domain.pk: str(domain)
            for domain in TechnicalDomain.objects.filter(
                pk__in=set(before["domains"]) | set(payload["domains"])
            ).select_related("skill_project")
        },
        "成员编号": {
            user.pk: f"{get_user_display_name(user)}（{user.username}）"
            for user in get_user_model().objects.filter(pk__in=set(before["members"]) | set(payload["members"]))
        },
        "额外权限编号": {
            permission.pk: permission_display_name(permission)
            for permission in Permission.objects.filter(
                pk__in=set(before["explicit_permissions"]) | set(payload["explicit_permissions"])
            ).select_related("content_type")
        },
    }
    for change in changes:
        mapping = display_maps.get(change["label"])
        if mapping is not None:
            for side in ("before", "after"):
                change[side] = "、".join(mapping.get(value, str(value)) for value in change[side]) or "无"
            change["label"] = change["label"].removesuffix("编号")
    return {"token": token, "changes": changes, "affected_count": len(set(before["members"]) | set(payload["members"]))}


@transaction.atomic
def save_role(*, actor, group, payload, token):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    try:
        preview = signing.loads(token, salt="accounts.role-preview", max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError("预览已失效，请重新预览。") from exc
    if group:
        group = Group.objects.select_for_update().get(pk=group.pk)
        # 与权限投影服务使用同一 Profile 行锁。
        list(GroupProfile.objects.select_for_update().filter(group=group))
    if preview != {"state": role_state(group), "payload": payload}:
        raise ValidationError("表单或现有授权在预览后发生变化，请重新预览。")
    if group is None:
        group = Group.objects.create(name=payload["name"])
    else:
        group.name = payload["name"]
        group.full_clean()
        group.save(update_fields=["name"])
    profile = ensure_group_profile(group)
    profile.description = payload["description"]
    profile.save(update_fields=["description"])
    sync_group_permission_assignments(
        group, payload["bundles"], Permission.objects.filter(pk__in=payload["explicit_permissions"])
    )
    TechnicalDomainGroupScope.objects.filter(group=group).exclude(technical_domain_id__in=payload["domains"]).delete()
    for domain_id in payload["domains"]:
        TechnicalDomainGroupScope.objects.get_or_create(group=group, technical_domain_id=domain_id)
    group.user_set.set(payload["members"])
    return group


def _user_roles_state(user, role_ids):
    groups = (
        Group.objects.filter(pk__in=role_ids)
        .select_related("profile")
        .prefetch_related(
            "permissions",
            "profile__explicit_permissions",
            "technical_domain_scopes",
        )
        .order_by("pk")
    )
    roles = []
    for group in groups:
        profile = getattr(group, "profile", None)
        roles.append(
            {
                "pk": group.pk,
                "name": group.name,
                "description": profile.description if profile else None,
                "codename": profile.codename if profile else None,
                "bundles": sorted(profile.selected_permission_bundles) if profile else [],
                "explicit": sorted(permission.pk for permission in profile.explicit_permissions.all())
                if profile
                else [],
                "permissions": sorted(permission.pk for permission in group.permissions.all()),
                "domains": sorted(scope.technical_domain_id for scope in group.technical_domain_scopes.all()),
            }
        )
    return {
        "user": user.pk,
        "groups": sorted(user.groups.values_list("pk", flat=True)),
        "roles": roles,
        "direct": sorted(user.user_permissions.values_list("pk", flat=True)),
        "active": user.is_active,
        "superuser": user.is_superuser,
    }


def preview_user_roles(*, actor, user, role_ids):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    selected = sorted(set(role_ids))
    current = set(user.groups.values_list("pk", flat=True))
    state = _user_roles_state(user, current | set(selected))
    token = signing.dumps({"state": state, "selected": selected}, salt="accounts.user-roles", compress=True)
    groups = {group.pk: group for group in Group.objects.filter(pk__in=current | set(selected))}
    if set(selected) - groups.keys():
        raise ValidationError("所选角色已不存在，请重新选择。")
    direct = set(state["direct"])
    before = set(Permission.objects.filter(group__pk__in=current).values_list("pk", flat=True)) | direct
    after = set(Permission.objects.filter(group__pk__in=selected).values_list("pk", flat=True)) | direct
    permission_names = {
        permission.pk: permission_display_name(permission)
        for permission in Permission.objects.filter(pk__in=before ^ after).select_related("content_type")
    }
    return {
        "token": token,
        "added": [groups[pk].name for pk in sorted(set(selected) - current)],
        "removed": [groups[pk].name for pk in sorted(current - set(selected))],
        "granted": [permission_names[pk] for pk in sorted(after - before)],
        "revoked": [permission_names[pk] for pk in sorted(before - after)],
    }


@transaction.atomic
def save_user_roles(*, actor, user, role_ids, token):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    try:
        preview = signing.loads(token, salt="accounts.user-roles", max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError("预览已失效，请重新预览。") from exc
    selected = sorted(set(role_ids))
    all_ids = set(user.groups.values_list("pk", flat=True)) | set(selected)
    list(Group.objects.select_for_update().filter(pk__in=all_ids).order_by("pk"))
    list(GroupProfile.objects.select_for_update().filter(group_id__in=all_ids).order_by("group_id"))
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if preview != {"state": _user_roles_state(user, all_ids), "selected": selected}:
        raise ValidationError("角色配置、用户授权或表单在预览后发生变化，请重新预览。")
    user.groups.set(selected)
    return user
