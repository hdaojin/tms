from core.tables import ActionsColumn, BaseTable

from .models import KnowledgeEvidence, KnowledgeEvidenceSkillMap


class KnowledgeEvidenceTable(BaseTable):
    actions = ActionsColumn(view_url="knowledge:evidence_detail", edit_url="knowledge:evidence_edit")

    class Meta(BaseTable.Meta):
        model = KnowledgeEvidence
        fields = ("skill_project", "capability_domain", "source_type", "title", "estimated_mark", "review_status", "actions")


class KnowledgeEvidenceSkillMapTable(BaseTable):
    actions = ActionsColumn(delete_url="knowledge:mapping_delete")

    class Meta(BaseTable.Meta):
        model = KnowledgeEvidenceSkillMap
        fields = ("evidence", "skill_node", "is_primary", "weight", "review_status", "actions")
