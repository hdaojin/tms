from core.tables import ActionsColumn, BaseDateColumn, BaseTable

from .models import TaskExecution, TrainingCycle, TrainingLog, TrainingPlan, TrainingTask


class TrainingCycleTable(BaseTable):
    start_date = BaseDateColumn()
    end_date = BaseDateColumn()
    actions = ActionsColumn("training:cycle_detail", "training:cycle_edit", edit_perm="training.change_trainingcycle")

    class Meta(BaseTable.Meta):
        model = TrainingCycle
        fields = ["code", "name", "skill_project", "start_date", "end_date", "status", "actions"]


class TrainingPlanTable(BaseTable):
    start_date = BaseDateColumn()
    end_date = BaseDateColumn()
    actions = ActionsColumn("training:plan_detail", "training:plan_edit", edit_perm="training.change_trainingplan")

    class Meta(BaseTable.Meta):
        model = TrainingPlan
        fields = ["title", "training_cycle", "start_date", "end_date", "status", "actions"]


class TrainingTaskTable(BaseTable):
    planned_date = BaseDateColumn()
    actions = ActionsColumn("training:task_detail", "training:task_edit", edit_perm="training.change_trainingtask")

    class Meta(BaseTable.Meta):
        model = TrainingTask
        fields = ["planned_date", "title", "training_plan", "priority", "status", "actions"]


class TaskExecutionTable(BaseTable):
    actions = ActionsColumn(
        "training:execution_detail", "training:execution_edit", edit_perm="training.change_taskexecution"
    )

    class Meta(BaseTable.Meta):
        model = TaskExecution
        fields = ["training_task", "user", "status", "actual_minutes", "actions"]


class TrainingLogTable(BaseTable):
    training_date = BaseDateColumn()
    actions = ActionsColumn("training:log_detail", "training:log_edit", edit_perm="training.change_traininglog")

    class Meta(BaseTable.Meta):
        model = TrainingLog
        fields = ["training_date", "training_cycle", "author", "topic", "actions"]
