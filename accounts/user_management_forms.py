from django import forms
from django.contrib.auth.models import Group

from core.utils.forms import StyledFormMixin


class UserFilterForm(forms.Form):
    q = forms.CharField(required=False)
    active = forms.ChoiceField(required=False, choices=[("", "全部状态"), ("1", "已激活"), ("0", "未激活")])
    role = forms.ChoiceField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [("", "全部角色"), ("none", "未分配")]
        self.fields["role"].choices += [
            (str(pk), name) for pk, name in Group.objects.order_by("name").values_list("pk", "name")
        ]


class UserManagementForm(StyledFormMixin, forms.Form):
    operation = forms.ChoiceField(
        label="管理操作",
        choices=[
            ("activate", "激活账号"),
            ("deactivate", "取消激活"),
            ("add_roles", "追加角色"),
            ("remove_roles", "移除角色"),
            ("set_leave_date", "填写离开日期"),
            ("clear_leave_date", "清空离开日期"),
        ],
    )
    roles = forms.ModelMultipleChoiceField(
        label="角色",
        queryset=Group.objects.order_by("name"),
        required=False,
        help_text="仅追加或移除角色时使用，可多选。",
    )
    leave_date = forms.DateField(
        label="离开日期",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text="仅填写离开日期时使用；清空日期请选择对应操作。",
    )

    def clean(self):
        cleaned = super().clean()
        operation = cleaned.get("operation")
        if operation in ("add_roles", "remove_roles") and not cleaned.get("roles"):
            self.add_error("roles", "请至少选择一个角色。")
        if operation == "set_leave_date" and not cleaned.get("leave_date"):
            self.add_error("leave_date", "请填写离开日期。")
        return cleaned

    def payload(self):
        operation = self.cleaned_data["operation"]
        return {
            "operation": operation,
            "roles": sorted(group.pk for group in self.cleaned_data["roles"])
            if operation in ("add_roles", "remove_roles")
            else [],
            "leave_date": self.cleaned_data["leave_date"].isoformat() if operation == "set_leave_date" else None,
        }


class UserActionForm(StyledFormMixin, forms.Form):
    """列表只选择操作，具体参数在中间页填写。"""

    operation = forms.ChoiceField(
        label="操作",
        choices=[("", "请选择操作"), *UserManagementForm.base_fields["operation"].choices],
        error_messages={"required": "请选择要执行的操作。"},
        widget=forms.Select(attrs={"class": "select-sm w-auto", "data-bulk-operation": ""}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operation"].widget.attrs["class"] = "select select-sm w-auto"
