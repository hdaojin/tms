from django.contrib import admin

from .models import GlossaryEntry, GlossaryEntryProposal, GlossaryImport, ProfessionalGlossary, StudyAttempt, StudySession


@admin.register(ProfessionalGlossary)
class ProfessionalGlossaryAdmin(admin.ModelAdmin):
    list_display = ("name", "skill_project", "is_active", "updated_at")
    list_filter = ("skill_project", "is_active")
    search_fields = ("name", "description")


@admin.register(GlossaryEntry)
class GlossaryEntryAdmin(admin.ModelAdmin):
    list_display = ("english_term", "acronym", "glossary", "source", "is_active")
    list_filter = ("glossary", "source", "is_active")
    search_fields = ("english_term", "acronym", "chinese_translation")
    readonly_fields = ("english_key", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GlossaryEntryProposal)
class GlossaryEntryProposalAdmin(admin.ModelAdmin):
    list_display = ("english_term", "glossary", "submitted_by", "status", "created_at")
    list_filter = ("glossary", "status")
    search_fields = ("english_term", "acronym", "chinese_translation", "submitted_by__username")
    readonly_fields = ("english_key", "created_at", "updated_at", "reviewed_at")


@admin.register(GlossaryImport)
class GlossaryImportAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "glossary", "imported_by", "status", "created_at")
    list_filter = ("glossary", "status")
    search_fields = ("original_filename", "sha256")
    readonly_fields = ("sha256", "parsed_payload", "decision_payload", "result_summary", "created_at", "confirmed_at")


@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    list_display = ("user", "glossary", "mode", "status", "started_at", "ended_at")
    list_filter = ("glossary", "mode", "status")
    search_fields = ("user__username", "glossary__name")
    readonly_fields = ("started_at", "ended_at")


@admin.register(StudyAttempt)
class StudyAttemptAdmin(admin.ModelAdmin):
    list_display = ("session", "sequence", "direction", "entry", "is_correct", "answered_at")
    list_filter = ("direction", "is_correct")
    search_fields = ("session__user__username", "entry__english_term", "submitted_answer")
    readonly_fields = ("presented_at", "answered_at")
