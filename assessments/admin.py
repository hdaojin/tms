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
    CompetitionPerson,
    CompetitionRole,
)

admin.site.register(
    [
        AssessmentSeries,
        AssessmentLevel,
        CompetitionPerson,
        CompetitionRole,
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
