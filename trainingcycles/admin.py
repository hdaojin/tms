from django.contrib import admin

from .models import TrainingCycle


@admin.register(TrainingCycle)
class TrainingCycleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'code',
        'project',
        'module_set',
        'status',
        'start_date',
        'end_date',
        'primary_competition_project',
        'reference_competition_project',
    )
    list_filter = ('status', 'project__competition_type', 'project', 'start_date')
    search_fields = (
        'name',
        'code',
        'project__name',
        'project__code',
        'primary_competition_project__competition__name',
        'reference_competition_project__competition__name',
    )
    autocomplete_fields = [
        'project',
        'module_set',
        'primary_competition_project',
        'reference_competition_project',
    ]
    list_select_related = (
        'project',
        'module_set',
        'primary_competition_project__competition',
        'reference_competition_project__competition',
    )
    date_hierarchy = 'start_date'
    ordering = ('-start_date', 'name')
