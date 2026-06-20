from core.tables import ActionsColumn, BaseTable

from .models import ScoringAspect, ScoringParticipant, ScoringScheme


class ScoringSchemeTable(BaseTable):
    actions = ActionsColumn(view_url="scoring:scheme_detail")

    class Meta(BaseTable.Meta):
        model = ScoringScheme
        fields = ("event_module", "module_code", "module_name", "total_mark", "parser_version", "actions")


class ScoringAspectTable(BaseTable):
    class Meta(BaseTable.Meta):
        model = ScoringAspect
        fields = ("code", "aspect_type", "description", "calculation_row", "max_mark", "source_row_number")


class ScoringParticipantTable(BaseTable):
    actions = ActionsColumn(view_url="scoring:participant_detail", edit_url="scoring:participant_edit")

    class Meta(BaseTable.Meta):
        model = ScoringParticipant
        fields = ("scheme", "display_name", "organization", "actions")
