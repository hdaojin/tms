from django.contrib import admin

from .models import (
    Assessment,
    AssessmentAward,
    AssessmentDocument,
    AssessmentFinalResult,
    AssessmentFinalScore,
    AssessmentLevel,
    AssessmentModule,
    AssessmentModuleCoach,
    AssessmentModuleDomain,
    AssessmentParticipant,
    AssessmentResultAward,
    AssessmentSeries,
    AssessmentType,
    CompetitionPerson,
    CompetitionRole,
)

class StableCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()


@admin.register(AssessmentType)
class AssessmentTypeAdmin(StableCodeAdmin):
    pass


@admin.register(CompetitionRole)
class CompetitionRoleAdmin(StableCodeAdmin):
    list_display = ("code", "name", "category", "order", "is_active")
    list_filter = ("category", "is_active")


admin.site.register(
    [
        AssessmentSeries,
        AssessmentLevel,
        CompetitionPerson,
        Assessment,
        AssessmentModule,
        AssessmentModuleDomain,
        AssessmentModuleCoach,
        AssessmentParticipant,
        AssessmentFinalResult,
        AssessmentFinalScore,
        AssessmentAward,
        AssessmentResultAward,
        AssessmentDocument,
    ]
)
