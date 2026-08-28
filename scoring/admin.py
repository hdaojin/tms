from django.contrib import admin

from .models import (
    JudgementOption,
    ScoringAspect,
    ScoringParserConfig,
    ScoringResult,
    ScoringResultImport,
    ScoringResultRevision,
    ScoringScheme,
    ScoringSchemeImport,
    ScoringSubCriterion,
)


@admin.register(ScoringParserConfig)
class ScoringParserConfigAdmin(admin.ModelAdmin):
    list_display = ('parser_key', 'display_name', 'is_enabled', 'is_default', 'order')
    list_filter = ('is_enabled', 'is_default')
    search_fields = ('parser_key', 'display_name', 'alias')

    def get_readonly_fields(self, request, obj=None):
        return ('parser_key',) if obj else ()


admin.site.register(
    [
        ScoringScheme,
        ScoringSchemeImport,
        ScoringSubCriterion,
        ScoringAspect,
        JudgementOption,
        ScoringResult,
        ScoringResultRevision,
        ScoringResultImport,
    ]
)
