from django.contrib import admin

from .models import (
    JudgementOption,
    MarkingAspect,
    MarkingAspectSkillNodeMap,
    MarkingParticipant,
    MarkingResult,
    MarkingResultImport,
    MarkingScheme,
    MarkingSchemeImport,
    MarkingSubCriterion,
)


class JudgementOptionInline(admin.TabularInline):
    model = JudgementOption
    extra = 0
    fields = ("score_value", "description", "sort_order", "source_row_number")
    readonly_fields = ("source_row_number",)


class MarkingAspectInline(admin.TabularInline):
    model = MarkingAspect
    extra = 0
    fields = ("code", "aspect_type", "description", "max_mark", "sort_order", "source_row_number")
    readonly_fields = ("source_row_number",)


@admin.register(MarkingSchemeImport)
class MarkingSchemeImportAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "status", "parser_version", "file_sha256", "uploaded_by", "uploaded_at")
    list_filter = ("status", "parser_version", "uploaded_at")
    search_fields = ("original_filename", "file_sha256")
    readonly_fields = ("file_sha256", "parse_summary", "uploaded_at")


@admin.register(MarkingScheme)
class MarkingSchemeAdmin(admin.ModelAdmin):
    list_display = ("module_code", "module_name", "total_mark", "standard_module", "created_at")
    list_filter = ("standard_module__project", "standard_module__module_set", "created_at")
    search_fields = ("title", "module_code", "module_name", "standard_module__name")
    autocomplete_fields = ("standard_module",)
    readonly_fields = ("parser_version", "created_at", "updated_at")
    inlines = [MarkingAspectInline]


@admin.register(MarkingSubCriterion)
class MarkingSubCriterionAdmin(admin.ModelAdmin):
    list_display = ("scheme", "code", "name", "day_of_marking", "sort_order")
    list_filter = ("scheme__standard_module__project",)
    search_fields = ("code", "name", "scheme__title")


@admin.register(MarkingAspect)
class MarkingAspectAdmin(admin.ModelAdmin):
    list_display = ("scheme", "code", "subcriterion", "aspect_type", "max_mark", "source_row_number")
    list_filter = ("aspect_type", "scheme__standard_module__project")
    search_fields = ("code", "description", "command", "requirement", "scheme__title")
    autocomplete_fields = ("scheme", "subcriterion")
    inlines = [JudgementOptionInline]


@admin.register(MarkingAspectSkillNodeMap)
class MarkingAspectSkillNodeMapAdmin(admin.ModelAdmin):
    list_display = ("aspect", "skill_node", "is_primary", "weight")
    list_filter = ("is_primary", "skill_node__tree__module__project")
    search_fields = ("aspect__code", "aspect__description", "skill_node__code", "skill_node__name")
    autocomplete_fields = ("aspect", "skill_node")


@admin.register(MarkingParticipant)
class MarkingParticipantAdmin(admin.ModelAdmin):
    list_display = ("scheme", "display_name", "external_identifier", "user", "competitor", "member_name")
    list_filter = ("scheme__standard_module__project",)
    search_fields = ("display_name", "external_identifier", "user__username", "competitor__name")
    autocomplete_fields = ("scheme", "user", "competitor")


@admin.register(MarkingResult)
class MarkingResultAdmin(admin.ModelAdmin):
    list_display = ("participant", "aspect", "score_awarded", "source", "graded_at")
    list_filter = ("source", "aspect__scheme__standard_module__project")
    search_fields = ("participant__display_name", "aspect__code", "aspect__description", "evidence")
    autocomplete_fields = ("participant", "aspect")


@admin.register(MarkingResultImport)
class MarkingResultImportAdmin(admin.ModelAdmin):
    list_display = ("scheme", "original_filename", "file_sha256", "imported_by", "imported_at")
    list_filter = ("imported_at", "scheme__standard_module__project")
    search_fields = ("original_filename", "file_sha256", "scheme__title")
    readonly_fields = ("file_sha256", "summary", "imported_at")
