from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .forms import (
    CompetitionLevelForm,
    CompetitionSeriesForm,
    EventForm,
    EventModuleCapabilityDomainMapForm,
    EventModuleForm,
    EventParticipantForm,
)
from .models import (
    CompetitionLevel,
    CompetitionSeries,
    Event,
    EventModule,
    EventModuleCapabilityDomainMap,
    EventParticipant,
)
from .tables import CompetitionLevelTable, CompetitionSeriesTable, EventModuleTable, EventParticipantTable, EventTable


class CompetitionSeriesListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = CompetitionSeries
    table_class = CompetitionSeriesTable
    template_name = "common/table_page.html"
    title = "赛事系列"
    title_icon = "icon-[tabler--trophy]"
    permission_required = "events.view_competitionseries"


class CompetitionSeriesDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = CompetitionSeries
    template_name = "events/series_detail.html"
    context_object_name = "series"
    title = "{name}"
    title_icon = "icon-[tabler--trophy]"
    permission_required = "events.view_competitionseries"


class CompetitionSeriesCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = CompetitionSeries
    form_class = CompetitionSeriesForm
    template_name = "common/form.html"
    permission_required = "events.add_competitionseries"
    title = "新增赛事系列"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("events:series_detail", args=[self.object.pk])


class CompetitionSeriesUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = CompetitionSeries
    form_class = CompetitionSeriesForm
    template_name = "common/form.html"
    permission_required = "events.change_competitionseries"
    title = "编辑赛事系列"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("events:series_detail", args=[self.object.pk])


class CompetitionLevelListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = CompetitionLevel
    table_class = CompetitionLevelTable
    template_name = "common/table_page.html"
    title = "赛事级别"
    title_icon = "icon-[tabler--stairs]"
    permission_required = "events.view_competitionlevel"


class CompetitionLevelDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = CompetitionLevel
    template_name = "events/level_detail.html"
    context_object_name = "level"
    title = "{name}"
    title_icon = "icon-[tabler--stairs]"
    permission_required = "events.view_competitionlevel"


class CompetitionLevelCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = CompetitionLevel
    form_class = CompetitionLevelForm
    template_name = "common/form.html"
    permission_required = "events.add_competitionlevel"
    title = "新增赛事级别"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("events:level_detail", args=[self.object.pk])


class CompetitionLevelUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = CompetitionLevel
    form_class = CompetitionLevelForm
    template_name = "common/form.html"
    permission_required = "events.change_competitionlevel"
    title = "编辑赛事级别"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("events:level_detail", args=[self.object.pk])


class EventListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = Event
    table_class = EventTable
    template_name = "events/event_list.html"
    title = "事件"
    title_icon = "icon-[tabler--calendar-event]"
    permission_required = "events.view_event"

    def get_queryset(self):
        return super().get_queryset().select_related("skill_project", "series", "level", "training_cycle")


class EventDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = Event
    template_name = "events/event_detail.html"
    context_object_name = "event"
    title = "{name}"
    title_icon = "icon-[tabler--calendar-event]"
    permission_required = "events.view_event"


class EventCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = "common/form.html"
    permission_required = "events.add_event"
    title = "新增事件"
    title_icon = "icon-[tabler--plus]"

    def form_valid(self, form):
        if form.instance.created_by_id is None:
            form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("events:event_detail", args=[self.object.pk])


class EventUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = "common/form.html"
    permission_required = "events.change_event"
    title = "编辑事件"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("events:event_detail", args=[self.object.pk])


class EventModuleListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = EventModule
    table_class = EventModuleTable
    template_name = "common/table_page.html"
    title = "事件模块"
    title_icon = "icon-[tabler--layout-grid]"
    permission_required = "events.view_eventmodule"


class EventModuleDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = EventModule
    template_name = "events/module_detail.html"
    context_object_name = "module"
    title = "{name}"
    title_icon = "icon-[tabler--layout-grid]"
    permission_required = "events.view_eventmodule"

    def get_queryset(self):
        return super().get_queryset().select_related("event", "event__skill_project").prefetch_related(
            "domain_mappings__capability_domain"
        )


class EventModuleCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = EventModule
    form_class = EventModuleForm
    template_name = "common/form.html"
    permission_required = "events.add_eventmodule"
    title = "新增事件模块"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("events:module_detail", args=[self.object.pk])


class EventModuleUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = EventModule
    form_class = EventModuleForm
    template_name = "common/form.html"
    permission_required = "events.change_eventmodule"
    title = "编辑事件模块"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("events:module_detail", args=[self.object.pk])


class EventModuleCapabilityDomainMapCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = EventModuleCapabilityDomainMap
    form_class = EventModuleCapabilityDomainMapForm
    template_name = "common/form.html"
    permission_required = "events.add_eventmodulecapabilitydomainmap"
    title = "新增能力领域映射"
    title_icon = "icon-[tabler--plus]"

    def dispatch(self, request, *args, **kwargs):
        self.event_module = EventModule.objects.select_related("event", "event__skill_project").get(
            pk=kwargs["module_pk"]
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["event_module"] = self.event_module
        return kwargs

    def form_valid(self, form):
        form.instance.event_module = self.event_module
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("events:module_detail", args=[self.event_module.pk])


class EventModuleCapabilityDomainMapUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = EventModuleCapabilityDomainMap
    form_class = EventModuleCapabilityDomainMapForm
    template_name = "common/form.html"
    permission_required = "events.change_eventmodulecapabilitydomainmap"
    title = "编辑能力领域映射"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("events:module_detail", args=[self.object.event_module_id])


class EventModuleCapabilityDomainMapDeleteView(TitleMixin, PermissionRequiredMixin, DeleteView):
    model = EventModuleCapabilityDomainMap
    template_name = "events/domain_map_confirm_delete.html"
    permission_required = "events.delete_eventmodulecapabilitydomainmap"
    title = "删除能力领域映射"
    title_icon = "icon-[tabler--trash]"

    def get_success_url(self):
        return reverse("events:module_detail", args=[self.object.event_module_id])


class EventParticipantListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = EventParticipant
    table_class = EventParticipantTable
    template_name = "common/table_page.html"
    title = "事件参与人员"
    title_icon = "icon-[tabler--users]"
    permission_required = "events.view_eventparticipant"


class EventParticipantDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = EventParticipant
    template_name = "events/participant_detail.html"
    context_object_name = "participant"
    title = "{display_name}"
    title_icon = "icon-[tabler--user]"
    permission_required = "events.view_eventparticipant"


class EventParticipantCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = EventParticipant
    form_class = EventParticipantForm
    template_name = "common/form.html"
    permission_required = "events.add_eventparticipant"
    title = "新增事件参与人员"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("events:participant_detail", args=[self.object.pk])


class EventParticipantUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = EventParticipant
    form_class = EventParticipantForm
    template_name = "common/form.html"
    permission_required = "events.change_eventparticipant"
    title = "编辑事件参与人员"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("events:participant_detail", args=[self.object.pk])

# Create your views here.
