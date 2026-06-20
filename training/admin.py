from django.contrib import admin

from .models import TrainingCycle, TrainingLog


@admin.register(TrainingCycle)
class TrainingCycleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "skill_project", "start_date", "end_date", "status")
    list_filter = ("skill_project", "status")
    search_fields = ("code", "name", "description")


@admin.register(TrainingLog)
class TrainingLogAdmin(admin.ModelAdmin):
    list_display = ("training_date", "topic", "training_cycle", "capability_domain", "uploaded_by")
    list_filter = ("training_cycle", "capability_domain", "training_date")
    search_fields = ("topic", "summary", "uploaded_by__username")
