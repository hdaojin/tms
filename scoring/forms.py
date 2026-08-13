from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from archives.models import ARCHIVE_ASSET_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from events.models import EventModule

from .models import ScoringParserConfig, ScoringParticipant, ScoringResult
from .services import default_parser_config, enabled_parser_configs


def event_module_choices_queryset():
    return EventModule.objects.select_related("event").order_by(
        "-event__start_date",
        "-event__created_at",
        "event__name",
        "event_id",
        "order",
        "code",
        "pk",
    )


class EventModuleChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.event.name} / {obj.code} - {obj.name}"


class ParserConfigChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.display_name


class ScoringImportForm(StyledFormMixin, forms.Form):
    event_module = EventModuleChoiceField(label="事件模块", queryset=EventModule.objects.none())
    parser_config = ParserConfigChoiceField(
        label="解析器",
        queryset=ScoringParserConfig.objects.none(),
        help_text="只显示已启用的评分表解析器。",
    )
    file = forms.FileField(
        label="评分表文件",
        validators=ARCHIVE_ASSET_UPLOAD_SPEC.validators(),
        widget=forms.ClearableFileInput(attrs=ARCHIVE_ASSET_UPLOAD_SPEC.widget_attrs(type="file")),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        event_modules = event_module_choices_queryset()
        self.fields["event_module"].queryset = event_modules
        queryset = enabled_parser_configs()
        self.fields["parser_config"].queryset = queryset
        if not self.is_bound:
            default_event_module = event_modules.first()
            if default_event_module:
                self.fields["event_module"].initial = default_event_module.pk
            default_config = default_parser_config()
            if default_config:
                self.fields["parser_config"].initial = default_config.pk


class ScoringParserConfigAdminForm(forms.ModelForm):
    class Meta:
        model = ScoringParserConfig
        fields = [
            "parser_key",
            "display_name",
            "alias",
            "description",
            "is_enabled",
            "is_default",
            "order",
        ]

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("is_default") and not cleaned_data.get("is_enabled"):
            raise ValidationError({"is_default": "默认解析器必须处于启用状态。"})
        return cleaned_data

    def _post_clean(self):
        requested_default = self.cleaned_data.get("is_default")
        if requested_default:
            self.cleaned_data["is_default"] = False
            self.instance.is_default = False
        try:
            super()._post_clean()
        finally:
            if requested_default:
                self.cleaned_data["is_default"] = True
                self.instance.is_default = True


class ScoringParticipantForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ScoringParticipant
        fields = ["scheme", "event_participant", "user", "external_identifier", "display_name", "organization", "order"]


class ScoringResultForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ScoringResult
        fields = ["participant", "aspect", "score_awarded", "source", "evidence", "graded_at"]
        widgets = {
            "graded_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "evidence": forms.Textarea(attrs={"rows": 3}),
        }
