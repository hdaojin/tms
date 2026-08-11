from core.tables import ActionsColumn, BaseDateTimeColumn, BaseTable

from .models import GlossaryEntry, GlossaryEntryProposal, GlossaryImport, ProfessionalGlossary, StudySession


class GlossaryBrowseTable(BaseTable):
    class Meta(BaseTable.Meta):
        model = GlossaryEntry
        fields = ("glossary", "english_term", "acronym", "chinese_translation")


class ProfessionalGlossaryTable(BaseTable):
    actions = ActionsColumn(view_url="glossary:manage_entry_list", edit_url="glossary:glossary_edit")

    class Meta(BaseTable.Meta):
        model = ProfessionalGlossary
        fields = ("skill_project", "name", "is_active", "updated_at", "actions")


class GlossaryEntryTable(BaseTable):
    actions = ActionsColumn(edit_url="glossary:entry_edit", edit_perm="glossary.change_glossaryentry")

    class Meta(BaseTable.Meta):
        model = GlossaryEntry
        fields = ("english_term", "acronym", "chinese_translation", "source", "is_active", "updated_at", "actions")


class ProposalTable(BaseTable):
    created_at = BaseDateTimeColumn()
    actions = ActionsColumn(view_url="glossary:proposal_detail")

    class Meta(BaseTable.Meta):
        model = GlossaryEntryProposal
        fields = ("english_term", "glossary", "submitted_by", "status", "created_at", "actions")


class GlossaryImportTable(BaseTable):
    created_at = BaseDateTimeColumn()
    actions = ActionsColumn(view_url="glossary:import_detail")

    class Meta(BaseTable.Meta):
        model = GlossaryImport
        fields = ("original_filename", "glossary", "imported_by", "status", "created_at", "actions")


class StudySessionTable(BaseTable):
    started_at = BaseDateTimeColumn()
    actions = ActionsColumn(view_url="glossary:session_summary", view_label="统计")

    class Meta(BaseTable.Meta):
        model = StudySession
        fields = ("user", "glossary", "mode", "target_count", "status", "started_at", "actions")
