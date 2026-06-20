from core.tables import ActionsColumn, BaseTable

from .models import ExamPaper, ExamRequirement


class ExamPaperTable(BaseTable):
    actions = ActionsColumn(view_url="examcontent:paper_detail", edit_url="examcontent:paper_edit")

    class Meta(BaseTable.Meta):
        model = ExamPaper
        fields = ("event_module", "title", "version", "language", "status", "actions")


class ExamRequirementTable(BaseTable):
    actions = ActionsColumn(view_url="examcontent:requirement_detail", edit_url="examcontent:requirement_edit")

    class Meta(BaseTable.Meta):
        model = ExamRequirement
        fields = ("paper", "capability_domain", "code", "title", "requirement_type", "is_explicitly_marked", "actions")
