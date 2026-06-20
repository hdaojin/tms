from django.contrib import admin

from .models import (
    JudgementOption,
    ScoringAspect,
    ScoringParticipant,
    ScoringParserConfig,
    ScoringResult,
    ScoringResultImport,
    ScoringScheme,
    ScoringSchemeImport,
    ScoringSubCriterion,
)


class ScoringSubCriterionInline(admin.TabularInline):
    model = ScoringSubCriterion
    extra = 0


@admin.register(ScoringScheme)
class ScoringSchemeAdmin(admin.ModelAdmin):
    list_display = ("title", "event_module", "module_code", "total_mark", "parser_version", "created_at")
    list_filter = ("event_module", "parser_version")
    search_fields = ("title", "module_code", "module_name")
    inlines = [ScoringSubCriterionInline]


@admin.register(ScoringAspect)
class ScoringAspectAdmin(admin.ModelAdmin):
    list_display = ("code", "scheme", "subcriterion", "aspect_type", "max_mark", "calculation_row", "source_row_number")
    list_filter = ("scheme", "aspect_type")
    search_fields = ("code", "description", "requirement", "calculation_row")


@admin.register(ScoringParserConfig)
class ScoringParserConfigAdmin(admin.ModelAdmin):
    list_display = ("parser_key", "display_name", "alias", "is_enabled", "is_default", "order", "updated_at")
    list_filter = ("is_enabled", "is_default")
    search_fields = ("parser_key", "display_name", "alias", "description")
    readonly_fields = ("parser_key", "created_at", "updated_at")
    fields = (
        "parser_key",
        "display_name",
        "alias",
        "description",
        "is_enabled",
        "is_default",
        "order",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScoringSchemeImport)
class ScoringSchemeImportAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "event_module",
        "module_code",
        "parser_display_name",
        "status",
        "imported_by",
        "imported_at",
        "confirmed_at",
    )
    list_filter = ("status", "parser_key", "event_module")
    search_fields = ("title", "module_code", "module_name", "parser_key", "parser_display_name")
    readonly_fields = (
        "event_module",
        "source_asset",
        "scheme",
        "status",
        "parser_key",
        "parser_display_name",
        "parser_alias",
        "parser_description",
        "title",
        "module_code",
        "module_name",
        "module_mark",
        "total_mark",
        "raw_snapshot",
        "field_mapping",
        "validation_report",
        "parsed_payload",
        "imported_by",
        "imported_at",
        "confirmed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(JudgementOption)
class JudgementOptionAdmin(admin.ModelAdmin):
    list_display = ("aspect", "score_value", "source_row_number", "order")
    search_fields = ("aspect__code", "description")


@admin.register(ScoringParticipant)
class ScoringParticipantAdmin(admin.ModelAdmin):
    list_display = ("display_name", "scheme", "event_participant", "user", "external_identifier")
    list_filter = ("scheme",)
    search_fields = ("display_name", "external_identifier", "user__username")


@admin.register(ScoringResult)
class ScoringResultAdmin(admin.ModelAdmin):
    list_display = ("participant", "aspect", "score_awarded", "source", "graded_at")
    list_filter = ("source", "participant__scheme")
    search_fields = ("participant__display_name", "aspect__code", "evidence")


@admin.register(ScoringResultImport)
class ScoringResultImportAdmin(admin.ModelAdmin):
    list_display = ("scheme", "source_asset", "imported_by", "imported_at")
    list_filter = ("scheme",)
