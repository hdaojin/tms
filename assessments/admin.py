from django.contrib import admin
from django.shortcuts import redirect
from core.utils.forms import ImmutableCodeFormMixin
from django import forms

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
        AssessmentModuleDomain,
        AssessmentModuleCoach,
        AssessmentParticipant,
        AssessmentFinalResult,
        AssessmentFinalScore,
        AssessmentAward,
        AssessmentResultAward,
    ]
)


class ImmutableCodeAdminForm(ImmutableCodeFormMixin, forms.ModelForm):
    pass


@admin.register(Assessment, AssessmentModule)
class ImmutableCodeAdmin(admin.ModelAdmin):
    form = ImmutableCodeAdminForm


@admin.register(AssessmentDocument)
class AssessmentDocumentAdmin(admin.ModelAdmin):
    """后台新增复用业务上传页，已保存文件与命名快照只读。"""

    def add_view(self, request, form_url="", extra_context=None):
        return redirect("assessments:document_upload")

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)
