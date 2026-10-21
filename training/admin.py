from django.contrib import admin
from accounts.services.users import get_user_display_name
from .models import (
    TaskExecution,
    TaskExecutionAttachment,
    TrainingCycle,
    TrainingCycleMember,
    TrainingCycleSkillTreeVersion,
    TrainingLog,
    TrainingLogExecution,
    TrainingPlan,
    TrainingTask,
    TrainingTaskAttachment,
    TrainingTaskCoach,
    TrainingTaskDomain,
    TrainingTaskSkill,
)

admin.site.register(
    [
        TrainingCycle,
        TrainingCycleSkillTreeVersion,
        TrainingCycleMember,
        TrainingPlan,
        TrainingTask,
        TrainingTaskDomain,
        TrainingTaskSkill,
        TrainingTaskCoach,
        TrainingTaskAttachment,
        TaskExecution,
        TaskExecutionAttachment,
        TrainingLogExecution,
    ]
)


@admin.register(TrainingLog)
class TrainingLogAdmin(admin.ModelAdmin):
    list_display = (
        "training_date", "training_cycle", "author_name", "topic", "has_document", "created_at", "updated_at",
    )
    list_select_related = ("training_cycle", "author")
    list_filter = ("training_cycle", "training_date")
    search_fields = (
        "topic", "summary", "author__first_name", "author__last_name", "author__username",
        "training_cycle__name", "training_cycle__code",
    )
    date_hierarchy = "training_date"
    readonly_fields = ("created_at", "updated_at")
    fields = ("training_cycle", "author", "training_date", "topic", "summary", "document", "created_at", "updated_at")

    @admin.display(description="作者", ordering="author__last_name")
    def author_name(self, obj):
        return get_user_display_name(obj.author)

    @admin.display(description="有附件", boolean=True)
    def has_document(self, obj):
        return bool(obj.document)
