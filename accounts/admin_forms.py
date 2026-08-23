from __future__ import annotations

from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Group, Permission

from accounts.services.permission_assignments import (
    get_group_explicit_permissions,
    get_group_permission_bundle_codes,
    get_user_explicit_permissions,
    get_user_permission_bundle_codes,
)
from core.permissions import get_permission_bundle_choices


class PermissionBundleField(forms.MultipleChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", "业务权限包")
        kwargs.setdefault("choices", get_permission_bundle_choices())
        kwargs.setdefault(
            "widget",
            FilteredSelectMultiple("业务权限包", is_stacked=False),
        )
        super().__init__(*args, **kwargs)


class GroupPermissionBundleAdminForm(forms.ModelForm):
    selected_permission_bundles = PermissionBundleField()
    explicit_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model", "codename"
        ),
        required=False,
        label="额外原生 Django 权限",
        help_text="仅选择业务权限包之外确实需要的权限。原始 Group.permissions 是自动生成的投影。",
        widget=FilteredSelectMultiple("额外原生 Django 权限", is_stacked=False),
    )

    class Meta:
        model = Group
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("permissions", None)
        if self.instance.pk:
            self.initial["selected_permission_bundles"] = get_group_permission_bundle_codes(self.instance)
            self.initial["explicit_permissions"] = get_group_explicit_permissions(self.instance)


class UserPermissionBundleAdminForm(UserChangeForm):
    selected_permission_bundles = PermissionBundleField()
    explicit_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model", "codename"
        ),
        required=False,
        label="额外原生 Django 权限",
        help_text="仅选择业务权限包之外确实需要的权限。原始 User.user_permissions 是自动生成的投影。",
        widget=FilteredSelectMultiple("额外原生 Django 权限", is_stacked=False),
    )

    class Meta(UserChangeForm.Meta):
        model = get_user_model()
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("user_permissions", None)
        self.fields["selected_permission_bundles"].help_text = (
            "需要技术领域范围的写权限必须由同一个用户组同时提供权限与技术领域范围；"
            "直接分配给用户的权限包不能绕过该限制。"
        )
        self.fields["explicit_permissions"].help_text = (
            "仅选择业务权限包之外确实需要的权限。原始 User.user_permissions 是自动生成的投影。"
            "技术领域写权限仍必须由同一个用户组同时提供权限与范围。"
        )
        if self.instance.pk:
            self.initial["selected_permission_bundles"] = get_user_permission_bundle_codes(self.instance)
            self.initial["explicit_permissions"] = get_user_explicit_permissions(self.instance)
