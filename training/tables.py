from pathlib import Path
from urllib.parse import urlencode

import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from accounts.services.users import get_user_display_name
from core.tables import ActionsColumn, BaseDateColumn, BaseDateTimeColumn, BaseTable

from .models import TaskExecution, TrainingCycle, TrainingCycleMember, TrainingLog, TrainingPlan, TrainingTask
from .log_management import can_manage_log_deletions


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
    actions = ActionsColumn("training:task_detail", "training:task_edit", edit_perm="training.change_trainingtask", edit_allowed_attr="can_edit")

    class Meta(BaseTable.Meta):
        model = TrainingTask
        fields = ["planned_date", "title", "training_plan", "priority", "status", "actions"]


class TaskExecutionTable(BaseTable):
    actions = ActionsColumn(
        "training:execution_detail", "training:execution_edit", edit_perm="training.change_taskexecution", edit_allowed_attr="can_edit"
    )

    class Meta(BaseTable.Meta):
        model = TaskExecution
        fields = ["training_task", "user", "status", "actual_minutes", "actions"]


class TrainingLogActionsColumn(ActionsColumn):
    def render(self, record, table, **kwargs):
        request = getattr(table, "request", None)
        user = getattr(request, "user", None)
        actions = [{"href": reverse("training:log_detail", args=[record.pk]), "label": "查看",
                    "variant_class": "btn-soft btn-primary"}]
        if user and user.has_perm("training.change_traininglog") and getattr(record, "can_edit", False):
            actions.append({"href": reverse("training:log_edit", args=[record.pk]), "label": "编辑",
                            "variant_class": "btn-soft btn-warning"})
        if user and can_manage_log_deletions(user):
            query = urlencode({"return_query": request.GET.urlencode()})
            actions.append({"href": reverse("training:log_delete", args=[record.pk]) + "?" + query,
                            "label": "删除", "variant_class": "btn-soft btn-error"})
        # 单条删除进入确认页，避免批量表单中嵌套行内弹窗的 POST 表单。
        return mark_safe(render_to_string("components/table_actions.html", {"actions": actions}, request=request))


class TrainingLogTable(BaseTable):
    selection = tables.CheckBoxColumn(accessor="pk", orderable=False, attrs={
        "th__input": {"class": "checkbox checkbox-sm", "aria-label": "全选当前页", "data-select-page": ""},
        "td__input": {"class": "checkbox checkbox-sm", "name": "logs", "aria-label": "选择日志", "data-row-selection": ""},
    })
    training_date = BaseDateColumn()
    member_role = tables.Column(verbose_name="周期身份", empty_values=())
    created_at = BaseDateTimeColumn(verbose_name="提交时间", format="Y-m-d H:i")

    document = tables.Column(verbose_name="日志附件", empty_values=(), orderable=False)
    actions = TrainingLogActionsColumn()

    def __init__(self, *args, **kwargs):
        self.can_bulk_delete = kwargs.pop("can_bulk_delete", False)
        super().__init__(*args, **kwargs)
        if not self.can_bulk_delete:
            self.columns.hide("selection")

    def render_member_role(self, value):
        return dict(TrainingCycleMember.Role.choices).get(value, "未关联")

    def render_created_at(self, value, record):
        displayed = timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
        if record.is_backfill:
            return format_html(
                '<span class="text-warning" title="历史补交日志的提交时间" aria-label="历史补交日志，提交时间{}">{}</span>',
                displayed, displayed,
            )
        return displayed

    def render_author(self, value):
        return get_user_display_name(value)

    def render_document(self, record):
        if not record.document:
            return "未附文件"
        return format_html(
            '<a class="link link-primary break-all" href="{}">{}</a>',
            reverse("training:log_detail", args=[record.pk]),
            Path(record.document.name).name,
        )

    class Meta(BaseTable.Meta):
        model = TrainingLog
        fields = ["selection", "training_date", "training_cycle", "author", "member_role", "created_at", "document", "actions"]
