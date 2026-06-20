from core.tables import ActionsColumn, BaseDateColumn, BaseTable

from .models import CompetitionLevel, CompetitionSeries, Event, EventModule, EventParticipant


class CompetitionSeriesTable(BaseTable):
    actions = ActionsColumn(view_url="events:series_detail", edit_url="events:series_edit")

    class Meta(BaseTable.Meta):
        model = CompetitionSeries
        fields = ("code", "name", "is_active", "actions")


class CompetitionLevelTable(BaseTable):
    actions = ActionsColumn(view_url="events:level_detail", edit_url="events:level_edit")

    class Meta(BaseTable.Meta):
        model = CompetitionLevel
        fields = ("code", "name", "weight", "is_active", "actions")


class EventTable(BaseTable):
    start_date = BaseDateColumn()
    actions = ActionsColumn(view_url="events:event_detail", edit_url="events:event_edit")

    class Meta(BaseTable.Meta):
        model = Event
        fields = ("code", "name", "skill_project", "event_type", "series", "level", "start_date", "status", "actions")


class EventModuleTable(BaseTable):
    actions = ActionsColumn(view_url="events:module_detail", edit_url="events:module_edit")

    class Meta(BaseTable.Meta):
        model = EventModule
        fields = ("event", "code", "name", "total_mark", "duration_minutes", "counts_towards_ranking", "actions")


class EventParticipantTable(BaseTable):
    actions = ActionsColumn(view_url="events:participant_detail", edit_url="events:participant_edit")

    class Meta(BaseTable.Meta):
        model = EventParticipant
        fields = ("event", "display_name", "role", "organization", "actions")
