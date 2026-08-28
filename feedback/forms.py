from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError

from core.constants import FEEDBACK_ATTACHMENT_MAX_COUNT, FEEDBACK_ATTACHMENT_MAX_TOTAL_SIZE_MB
from core.forms.fields import MultipleFileField
from core.uploads import FEEDBACK_ATTACHMENT_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin

from .models import FeedbackCategory, FeedbackStatus
from .services import validate_feedback_attachments


class FeedbackForm(StyledFormMixin, forms.Form):
    category = forms.ModelChoiceField(
        label="反馈类型",
        queryset=FeedbackCategory.objects.none(),
        to_field_name="code",
    )
    title = forms.CharField(label="标题", max_length=200)
    content = forms.CharField(label="详细描述", widget=forms.Textarea(attrs={"rows": 8}))
    attachments = MultipleFileField(
        label="附件",
        upload_spec=FEEDBACK_ATTACHMENT_UPLOAD_SPEC,
        required=False,
        help_text=FEEDBACK_ATTACHMENT_UPLOAD_SPEC.help_text("上传附件"),
    )
    is_anonymous = forms.BooleanField(label="匿名提交", required=False)
    is_private = forms.BooleanField(label="仅工作人员可见", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = FeedbackCategory.objects.filter(is_active=True)
        self.fields["category"].queryset = categories
        private_codes = categories.filter(default_private=True).values_list("code", flat=True)
        self.fields["category"].widget.attrs.update(
            {
                "x-ref": "category",
                "x-on:change": "categoryChanged",
                "data-default-private-values": json.dumps(list(private_codes)),
            }
        )
        self.fields["is_private"].widget.attrs.update({"x-ref": "private", "x-on:change": "privateChanged"})
        self.fields["attachments"].widget.attrs.update(
            {
                "data-upload-max-files": str(FEEDBACK_ATTACHMENT_MAX_COUNT),
                "data-upload-max-total-size-mb": str(FEEDBACK_ATTACHMENT_MAX_TOTAL_SIZE_MB),
            }
        )
        initial_category = self.initial.get("category")
        if not self.is_bound and initial_category:
            initial_code = getattr(initial_category, "code", initial_category)
            if categories.filter(code=initial_code, default_private=True).exists():
                self.fields["is_private"].initial = True

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("标题不能为空。")
        return title

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if not content:
            raise forms.ValidationError("详细描述不能为空。")
        return content

    def clean(self):
        cleaned_data = super().clean()
        if "attachments" in cleaned_data:
            try:
                validate_feedback_attachments(cleaned_data["attachments"])
            except ValidationError as exc:
                self.add_error("attachments", exc)
        return cleaned_data


class FeedbackReplyForm(StyledFormMixin, forms.Form):
    content = forms.CharField(label="回复内容", widget=forms.Textarea(attrs={"rows": 5}))
    attachments = MultipleFileField(
        label="附件",
        upload_spec=FEEDBACK_ATTACHMENT_UPLOAD_SPEC,
        required=False,
        help_text=FEEDBACK_ATTACHMENT_UPLOAD_SPEC.help_text("上传附件"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attachments"].widget.attrs.update(
            {
                "data-upload-max-files": str(FEEDBACK_ATTACHMENT_MAX_COUNT),
                "data-upload-max-total-size-mb": str(FEEDBACK_ATTACHMENT_MAX_TOTAL_SIZE_MB),
            }
        )

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if not content:
            raise forms.ValidationError("回复内容不能为空。")
        return content

    def clean(self):
        cleaned_data = super().clean()
        if "attachments" in cleaned_data:
            try:
                validate_feedback_attachments(cleaned_data["attachments"])
            except ValidationError as exc:
                self.add_error("attachments", exc)
        return cleaned_data


class FeedbackManageForm(StyledFormMixin, forms.Form):
    status = forms.ChoiceField(label="状态", choices=FeedbackStatus.choices)
    resolution = forms.CharField(label="处理结果", required=False, widget=forms.Textarea(attrs={"rows": 5}))

    def clean_resolution(self):
        return self.cleaned_data["resolution"].strip()

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("status") in {FeedbackStatus.RESOLVED, FeedbackStatus.CLOSED}
            and not cleaned_data.get("resolution")
        ):
            self.add_error("resolution", "已解决或已关闭的反馈必须填写处理结果。")
        return cleaned_data
