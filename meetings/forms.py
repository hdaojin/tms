from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q

from accounts.services.users import get_user_full_info

from .models import Meeting

from core.uploads import MEETING_FILE_UPLOAD_SPEC
from core.utils.forms import DefaultTodayDateFormMixin, StyledFormMixin
from .selectors import recipient_queryset
from .widgets import RecipientSelect


class MeetingAudienceForm(StyledFormMixin, forms.ModelForm):
    visible_groups = forms.ModelMultipleChoiceField(
        label="可见角色",
        queryset=Group.objects.order_by("name", "pk"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    visible_users = forms.ModelMultipleChoiceField(
        label="指定人员",
        queryset=get_user_model().objects.none(),
        required=False,
        widget=RecipientSelect,
        help_text="按姓名或账号搜索，可多选。",
    )

    class Meta:
        model = Meeting
        fields = ["is_public", "visible_groups", "visible_users"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "visible_users" not in self.fields:
            return
        existing_ids = list(self.instance.visible_users.values_list("pk", flat=True)) if self.instance.pk else []
        eligible = recipient_queryset()
        eligible_ids = eligible.values("pk")
        self.fields["visible_users"].queryset = get_user_model().objects.filter(
            Q(pk__in=eligible_ids) | Q(pk__in=existing_ids)
        )
        field = self.fields["visible_users"]
        selected_ids = self["visible_users"].value()
        selected_ids = [str(pk) for pk in (selected_ids or []) if str(pk).isdecimal()]
        selected = list(field.queryset.filter(pk__in=selected_ids).order_by("last_name", "first_name", "username"))
        allowed_ids = set(eligible.filter(pk__in=[user.pk for user in selected]).values_list("pk", flat=True))
        field.widget.selected = [
            {"id": user.pk, "label": get_user_full_info(user), "unavailable": user.pk not in allowed_ids}
            for user in selected
        ]
        field.widget.meeting_id = self.instance.pk or ""

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_public"):
            cleaned["visible_groups"] = Group.objects.none()
            cleaned["visible_users"] = get_user_model().objects.none()
        elif not self.errors and not cleaned.get("visible_groups") and not cleaned.get("visible_users"):
            raise forms.ValidationError("取消“所有人”后，请至少选择一个角色或指定人员。")
        return cleaned


class MeetingListFilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=200, label="关键词")
    date_from = forms.DateField(required=False, label="会议起日", input_formats=["%Y-%m-%d"])
    date_to = forms.DateField(required=False, label="会议止日", input_formats=["%Y-%m-%d"])

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("date_from") and cleaned.get("date_to") and cleaned["date_from"] > cleaned["date_to"]:
            raise forms.ValidationError("会议起日不能晚于止日。")
        return cleaned


class MeetingUploadForm(DefaultTodayDateFormMixin, MeetingAudienceForm):
    default_today_date_fields = ('date',)

    class Meta(MeetingAudienceForm.Meta):
        model = Meeting
        fields = ['title', 'date', 'file', 'is_public', 'visible_groups', 'visible_users']
        localized_fields = ['date']  # 使用本地化日期输入
        widgets = {
            'title': forms.TextInput(
                attrs={'type': 'text', 'aria-label': 'title-input', 'placeholder': '例如: 网络系统管理项目周例会'}
            ),
            'date': forms.DateInput(attrs={'type': 'date', 'aria-label': 'date-input'}),
            'file': forms.FileInput(
                attrs=MEETING_FILE_UPLOAD_SPEC.widget_attrs(
                    type='file',
                    **{'aria-label': 'file-input'},
                )
            ),
        }
        labels = {
            'title': '会议名称',
            'date': '会议日期',
            'file': '会议记录文件',
        }
