from __future__ import annotations

from django import forms

from archives.models import ARCHIVE_ASSET_UPLOAD_SPEC
from core.utils.forms import DefaultTodayDateFormMixin, StyledFormMixin

from .models import TrainingCycle, TrainingLog


class TrainingCycleForm(DefaultTodayDateFormMixin, StyledFormMixin, forms.ModelForm):
    default_today_date_fields = ("start_date",)

    class Meta:
        model = TrainingCycle
        fields = ["skill_project", "code", "name", "start_date", "end_date", "status", "description"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class TrainingLogForm(DefaultTodayDateFormMixin, StyledFormMixin, forms.ModelForm):
    default_today_date_fields = ("training_date",)
    file = forms.FileField(
        label="训练日志文件",
        validators=ARCHIVE_ASSET_UPLOAD_SPEC.validators(),
        widget=forms.ClearableFileInput(attrs=ARCHIVE_ASSET_UPLOAD_SPEC.widget_attrs(type="file")),
    )

    class Meta:
        model = TrainingLog
        fields = ["training_cycle", "capability_domain", "training_date", "topic", "summary"]
        widgets = {
            "training_date": forms.DateInput(attrs={"type": "date"}),
            "summary": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned = super().clean()
        cycle = cleaned.get("training_cycle")
        domain = cleaned.get("capability_domain")
        if cycle and domain and cycle.skill_project_id != domain.skill_project_id:
            self.add_error("capability_domain", "能力领域必须属于训练周期对应的技能项目。")
        return cleaned


class TrainingLogUpdateForm(TrainingLogForm):
    file = None
