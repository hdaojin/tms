from core.tables import ActionsColumn, BaseDateColumn, BaseTable
from .models import Assessment, AssessmentModule, AssessmentParticipant


class AssessmentTable(BaseTable):
    start_date = BaseDateColumn()
    end_date = BaseDateColumn()
    actions = ActionsColumn(
        "assessments:assessment_detail", "assessments:assessment_edit", edit_perm="assessments.change_assessment"
    )

    class Meta(BaseTable.Meta):
        model = Assessment
        fields = ["code", "name", "assessment_type", "start_date", "end_date", "status", "actions"]


class AssessmentModuleTable(BaseTable):
    actions = ActionsColumn(
        "assessments:module_detail", "assessments:module_edit", edit_perm="assessments.change_assessmentmodule"
    )

    class Meta(BaseTable.Meta):
        model = AssessmentModule
        fields = ["assessment", "code", "name", "total_mark", "duration_minutes", "actions"]


class AssessmentParticipantTable(BaseTable):
    actions = ActionsColumn("assessments:participant_detail")

    class Meta(BaseTable.Meta):
        model = AssessmentParticipant
        fields = ["assessment", "display_name", "role", "organization", "actions"]
