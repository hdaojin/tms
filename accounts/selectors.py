from django.contrib.auth.models import Permission

from accounts.models import UserProfile
from core.permissions import get_permission_bundle_spec_map


def permission_display_name(permission):
    model = permission.content_type.model_class()
    if model is not None:
        for action, label in (("view", "查看"), ("add", "新增"), ("change", "修改"), ("delete", "删除")):
            if permission.codename == f"{action}_{model._meta.model_name}":
                return f"{label}{model._meta.verbose_name}"
    return permission.name


def permission_diagnostics(user):
    """仅供有诊断权限的页面调用；按来源列出实际原生权限，不从包名推断生效状态。"""
    specs = get_permission_bundle_spec_map()
    groups = list(
        user.groups.select_related("profile").prefetch_related(
            "permissions__content_type",
            "profile__explicit_permissions__content_type",
            "technical_domain_scopes__technical_domain__skill_project",
        )
    )
    labels = {}
    sources = []

    def source(name, permissions, bundles, domains, explicit):
        actual = []
        for permission in permissions:
            label = f"{permission.content_type.app_label}.{permission.codename}"
            actual.append(label)
            labels.setdefault(label, {"name": permission_display_name(permission), "sources": []})["sources"].append(
                name
            )
        return {
            "name": name,
            "permissions": sorted(actual),
            "bundles": [specs[code].name if code in specs else f"未知权限包：{code}" for code in bundles],
            "domains": domains,
            "explicit": [permission_display_name(permission) for permission in explicit],
        }

    for group in groups:
        profile = getattr(group, "profile", None)
        domains = [str(scope.technical_domain) for scope in group.technical_domain_scopes.all()]
        sources.append(
            source(
                group.name,
                group.permissions.all(),
                profile.selected_permission_bundles if profile else [],
                domains,
                list(profile.explicit_permissions.all()) if profile else [],
            )
        )
    profile = UserProfile.objects.filter(user=user).prefetch_related("explicit_permissions__content_type").first()
    sources.append(
        source(
            "个人直接授权",
            user.user_permissions.select_related("content_type"),
            profile.selected_permission_bundles if profile else [],
            [],
            list(profile.explicit_permissions.all()) if profile else [],
        )
    )
    if user.is_active and user.is_superuser:
        source("超级管理员", Permission.objects.select_related("content_type"), [], [], [])
    return {
        "sources": sources,
        "permissions": [{"label": label, **data} for label, data in sorted(labels.items())],
        "active": user.is_active,
        "superuser": user.is_superuser,
    }
