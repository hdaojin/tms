from django.contrib import admin

from .models import ExamPaper, ExamRequirement


@admin.register(ExamPaper)
class ExamPaperAdmin(admin.ModelAdmin):
    list_display = ("title", "event_module", "version", "language", "status", "created_at")
    list_filter = ("event_module", "status", "language")
    search_fields = ("title", "version")


@admin.register(ExamRequirement)
class ExamRequirementAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "paper", "capability_domain", "requirement_type", "extraction_source")
    list_filter = ("paper", "capability_domain", "requirement_type", "extraction_source")
    search_fields = ("code", "title", "original_text", "normalized_text")
