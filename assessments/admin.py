from django.contrib import admin

from .models import (
    Assessment,
    AssessmentDocument,
    AssessmentLevel,
    AssessmentModule,
    AssessmentModuleCoach,
    AssessmentModuleDomain,
    AssessmentParticipant,
    AssessmentResultSummary,
    AssessmentSeries,
)

admin.site.register(
    [
        AssessmentSeries,
        AssessmentLevel,
        Assessment,
        AssessmentModule,
        AssessmentModuleDomain,
        AssessmentModuleCoach,
        AssessmentParticipant,
        AssessmentResultSummary,
        AssessmentDocument,
    ]
)
