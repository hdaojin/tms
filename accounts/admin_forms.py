from __future__ import annotations

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Group
from django.utils.html import format_html, format_html_join

from accounts.services.permission_bundles import (
    get_group_extra_permissions,
    get_group_permission_bundle_codes,
    get_user_extra_permissions,
    get_user_permission_bundle_codes,
)
from core.permissions import get_permission_bundle_choices, get_permission_bundle_specs


def _build_permission_bundle_help_text():
    items = format_html_join(
        "",
        "<li><strong>{}</strong>：{} 自动附加 {}</li>",
        (
            (spec.name, spec.description, "、".join(spec.permission_labels))
            for spec in get_permission_bundle_specs()
        ),
    )
    return format_html(
        "勾选业务权限包后，系统会自动补齐底层 Django 权限。<ul>{}</ul>",
        items,
    )


class PermissionBundleField(forms.MultipleChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", "业务权限包")
        kwargs.setdefault("choices", get_permission_bundle_choices())
        kwargs.setdefault("help_text", _build_permission_bundle_help_text())
        kwargs.setdefault(
            "widget",
            FilteredSelectMultiple("业务权限包", is_stacked=False),
        )
        super().__init__(*args, **kwargs)


class GroupPermissionBundleAdminForm(forms.ModelForm):
    selected_permission_bundles = PermissionBundleField()

    class Meta:
        model = Group
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "permissions" in self.fields:
            self.fields["permissions"].label = "额外原生权限"
            self.fields["permissions"].help_text = (
                "这里只需要选择业务权限包之外的额外权限；系统会自动补齐业务权限包依赖的底层权限。"
            )
        if self.instance.pk:
            self.initial["selected_permission_bundles"] = get_group_permission_bundle_codes(self.instance)
            self.fields["permissions"].initial = get_group_extra_permissions(self.instance)


class UserPermissionBundleAdminForm(UserChangeForm):
    selected_permission_bundles = PermissionBundleField()

    class Meta(UserChangeForm.Meta):
        model = get_user_model()
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "user_permissions" in self.fields:
            self.fields["user_permissions"].label = "额外原生权限"
            self.fields["user_permissions"].help_text = (
                "这里只需要选择业务权限包之外直接授予当前用户的额外权限；系统会自动补齐业务权限包依赖的底层权限。"
            )
        if self.instance.pk:
            self.initial["selected_permission_bundles"] = get_user_permission_bundle_codes(self.instance)
            self.fields["user_permissions"].initial = get_user_extra_permissions(self.instance)