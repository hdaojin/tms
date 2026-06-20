from django.contrib import admin

from .models import (
    CompetitionLevel,
    CompetitionSeries,
    Event,
    EventModule,
    EventModuleCapabilityDomainMap,
    EventParticipant,
    EventResultSummary,
)


@admin.register(CompetitionSeries)
class CompetitionSeriesAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(CompetitionLevel)
class CompetitionLevelAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "weight", "is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "skill_project", "series", "level", "event_type", "status", "start_date")
    list_filter = ("skill_project", "series", "level", "event_type", "status")
    search_fields = ("code", "name", "location")


@admin.register(EventModule)
class EventModuleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "event", "total_mark", "duration_minutes", "counts_towards_ranking")
    list_filter = ("event", "counts_towards_ranking")
    search_fields = ("code", "name", "event__name")


@admin.register(EventModuleCapabilityDomainMap)
class EventModuleCapabilityDomainMapAdmin(admin.ModelAdmin):
    list_display = ("event_module", "capability_domain", "is_primary", "weight")
    list_filter = ("is_primary", "capability_domain")
    search_fields = ("event_module__name", "capability_domain__name")


@admin.register(EventParticipant)
class EventParticipantAdmin(admin.ModelAdmin):
    list_display = ("display_name", "event", "role", "external_code", "user", "organization")
    list_filter = ("event", "role")
    search_fields = ("display_name", "external_code", "organization", "user__username")


@admin.register(EventResultSummary)
class EventResultSummaryAdmin(admin.ModelAdmin):
    list_display = ("event", "participant", "total_score", "rank", "award")
    list_filter = ("event", "award")
    search_fields = ("participant__display_name", "award")
