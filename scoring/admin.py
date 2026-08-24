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


admin.site.register(
    [
        ScoringScheme,
        ScoringParserConfig,
        ScoringSchemeImport,
        ScoringSubCriterion,
        ScoringAspect,
        JudgementOption,
        ScoringResult,
        ScoringResultRevision,
        ScoringResultImport,
    ]
)
