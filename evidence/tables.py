from core.tables import ActionsColumn, BaseTable
from .models import KnowledgeEvidence


class KnowledgeEvidenceTable(BaseTable):
    actions = ActionsColumn(
        "evidence:evidence_detail", "evidence:evidence_edit", edit_perm="evidence.change_knowledgeevidence", edit_allowed_attr="can_edit"
    )

    class Meta(BaseTable.Meta):
        model = KnowledgeEvidence
        fields = ["title", "skill_project", "assessment_module", "source_type", "review_status", "actions"]
