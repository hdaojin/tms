from django.contrib import admin

from .models import (
    JudgementOption,
    ScoringAspect,
    ScoringParserConfig,
    ScoringParticipant,
    ScoringResult,
    ScoringResultImport,
    ScoringScheme,
    ScoringSchemeImport,
    ScoringSubCriterion,
)


admin.site.register(
    [
        ScoringScheme,
        ScoringParserConfig,
        ScoringSchemeImport,
        ScoringSubCriterion,
        ScoringAspect,
        JudgementOption,
        ScoringParticipant,
        ScoringResult,
        ScoringResultImport,
    ]
)
