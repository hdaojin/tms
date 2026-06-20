from django.contrib import admin

from .models import KnowledgeEvidence, KnowledgeEvidenceSkillMap


@admin.register(KnowledgeEvidence)
class KnowledgeEvidenceAdmin(admin.ModelAdmin):
    list_display = ("title", "skill_project", "capability_domain", "source_type", "estimated_mark", "review_status")
    list_filter = ("skill_project", "capability_domain", "source_type", "review_status", "extraction_source")
    search_fields = ("title", "original_text", "normalized_text")
    readonly_fields = ("created_at", "updated_at", "reviewed_at")


@admin.register(KnowledgeEvidenceSkillMap)
class KnowledgeEvidenceSkillMapAdmin(admin.ModelAdmin):
    list_display = ("evidence", "skill_node", "is_primary", "weight", "mapping_source", "review_status")
    list_filter = ("is_primary", "mapping_source", "review_status", "skill_node__tree_version")
    search_fields = ("evidence__title", "skill_node__code", "skill_node__name")
