from django.contrib import admin
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
        TrainingLog,
        TrainingLogExecution,
    ]
)
