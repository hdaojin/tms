from __future__ import annotations

from django import forms

from core.utils.forms import DefaultTodayDateFormMixin, StyledFormMixin

from .models import CompetitionLevel, CompetitionSeries, Event, EventModule, EventModuleCapabilityDomainMap, EventParticipant


class CompetitionSeriesForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CompetitionSeries
        fields = ["code", "name", "description", "order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class CompetitionLevelForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CompetitionLevel
        fields = ["code", "name", "weight", "order", "is_active"]


class EventForm(DefaultTodayDateFormMixin, StyledFormMixin, forms.ModelForm):
    default_today_date_fields = ("start_date",)

    class Meta:
        model = Event
        fields = [
            "skill_project",
            "series",
            "level",
            "training_cycle",
            "event_type",
            "name",
            "code",
            "start_date",
            "end_date",
            "location",
            "description",
            "status",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class EventModuleForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EventModule
        fields = ["event", "code", "name", "description", "order", "total_mark", "duration_minutes", "counts_towards_ranking"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class EventModuleCapabilityDomainMapForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EventModuleCapabilityDomainMap
        fields = ["event_module", "capability_domain", "is_primary", "weight", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, event_module=None, **kwargs):
        super().__init__(*args, **kwargs)
        if event_module is not None:
            self.fields["event_module"].initial = event_module
            self.fields["event_module"].queryset = EventModule.objects.filter(pk=event_module.pk)
            self.fields["event_module"].disabled = True
            self.fields["capability_domain"].queryset = event_module.event.skill_project.capability_domains.filter(
                is_active=True
            )
        elif self.instance.pk:
            project = self.instance.event_module.event.skill_project
            self.fields["capability_domain"].queryset = project.capability_domains.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        event_module = cleaned.get("event_module")
        capability_domain = cleaned.get("capability_domain")
        if event_module and capability_domain and event_module.event.skill_project_id != capability_domain.skill_project_id:
            self.add_error("capability_domain", "能力领域必须属于事件对应的技能项目。")
        return cleaned


class EventParticipantForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EventParticipant
        fields = ["event", "user", "external_code", "display_name", "role", "organization"]
