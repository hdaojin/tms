from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

from core.permissions import get_permission_bundle_choices
from core.utils.forms import StyledFormMixin
from accounts.services.users import get_user_full_info
from accounts.selectors import permission_display_name
from standards.models import TechnicalDomain


class UserRolesForm(StyledFormMixin, forms.Form):
    roles = forms.ModelMultipleChoiceField(
        label="所属角色",
        queryset=Group.objects.order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox checkbox-primary"}),
    )


class RoleForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label="角色名称", max_length=150)
    description = forms.CharField(label="职责说明", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    bundles = forms.MultipleChoiceField(label="业务权限包", required=False, widget=forms.CheckboxSelectMultiple)
    domains = forms.ModelMultipleChoiceField(
        label="技术领域范围",
        queryset=TechnicalDomain.objects.select_related("skill_project"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    members = forms.ModelMultipleChoiceField(
        label="角色成员",
        queryset=get_user_model().objects.order_by("username"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    explicit_permissions = forms.ModelMultipleChoiceField(
        label="额外原生权限",
        queryset=Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename"),
        required=False,
    )

    def __init__(self, *args, group=None, **kwargs):
        self.group = group
        super().__init__(*args, **kwargs)
        self.fields["bundles"].choices = get_permission_bundle_choices()
        self.fields["bundles"].widget.attrs["class"] = "checkbox checkbox-primary mt-1 shrink-0"
        self.fields["members"].widget.attrs["class"] = "checkbox checkbox-primary"
        self.fields["members"].label_from_instance = get_user_full_info
        self.fields["explicit_permissions"].widget.attrs["size"] = 10
        self.fields["explicit_permissions"].label_from_instance = lambda permission: (
            f"{permission_display_name(permission)}（{permission.content_type.app_label}.{permission.codename}）"
        )
        self.fields[
            "domains"
        ].help_text = "同组同时提供权限与领域才生效；空范围不授予领域维护能力。跨领域对象仍可能要求显式教练分配。"
        self.fields[
            "members"
        ].help_text = "勾选需要加入的成员；用户可同时加入多个角色。不会自动设置周期身份、当前周期或任务教练。"
        self.fields[
            "explicit_permissions"
        ].help_text = "用于权限包未覆盖的特殊能力。移除权限包不会撤销这里独立授予的权限。"

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        existing = Group.objects.filter(name=name)
        if self.group:
            existing = existing.exclude(pk=self.group.pk)
        if existing.exists():
            raise forms.ValidationError("此角色名称已存在。")
        return name

    def payload(self):
        data = self.cleaned_data
        return {
            "name": data["name"],
            "description": data["description"],
            "bundles": sorted(data["bundles"]),
            **{key: sorted(obj.pk for obj in data[key]) for key in ("domains", "members", "explicit_permissions")},
        }
