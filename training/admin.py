from django.contrib import admin
from .models import (
    TaskExecution,
    TaskExecutionAttachment,
    TrainingCycle,
    TrainingCycleMember,
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
        TrainingCycleMember,
        TrainingPlan,
        TrainingTask,
        TrainingTaskDomain,
        TrainingTaskSkill,
        TrainingTaskCoach,
        TrainingTaskAttachment,
        TaskExecution,
        TaskExecutionAttachment,
        TrainingLog,
        TrainingLogExecution,
    ]
)
