from core.tables import ActionsColumn, BaseDateColumn, BaseTable
from .models import Assessment, AssessmentModule, AssessmentParticipant, CompetitionPerson, CompetitionRole


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


class CompetitionPersonTable(BaseTable):
    actions = ActionsColumn(
        edit_url="assessments:competition_person_edit",
        edit_perm="assessments.change_competitionperson",
    )

    class Meta(BaseTable.Meta):
        model = CompetitionPerson
        fields = ["name", "organization", "country_or_region", "title", "email", "is_active", "actions"]


class CompetitionRoleTable(BaseTable):
    actions = ActionsColumn(
        edit_url="assessments:competition_role_edit",
        edit_perm="assessments.change_competitionrole",
    )

    class Meta(BaseTable.Meta):
        model = CompetitionRole
        fields = ["code", "name", "category", "order", "is_active", "actions"]
