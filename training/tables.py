from core.tables import ActionsColumn, BaseDateColumn, BaseTable

from .models import TrainingCycle, TrainingLog


class TrainingCycleTable(BaseTable):
    start_date = BaseDateColumn()
    end_date = BaseDateColumn()
    actions = ActionsColumn(view_url="training:cycle_detail", edit_url="training:cycle_edit")

    class Meta(BaseTable.Meta):
        model = TrainingCycle
        fields = ("code", "name", "skill_project", "start_date", "end_date", "status", "actions")


class TrainingLogTable(BaseTable):
    training_date = BaseDateColumn()
    actions = ActionsColumn(view_url="training:log_detail", edit_url="training:log_edit")

    class Meta(BaseTable.Meta):
        model = TrainingLog
        fields = ("training_date", "training_cycle", "capability_domain", "topic", "uploaded_by", "actions")
