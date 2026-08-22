from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from pathlib import Path

from django.http import FileResponse, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DetailView, FormView, UpdateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .forms import (
    CoachFeedbackForm,
    TaskExecutionForm,
    TrainingCycleForm,
    TrainingLogForm,
    TrainingPlanForm,
    TrainingTaskForm,
)
from .models import TaskExecution, TrainingCycle, TrainingLog, TrainingPlan, TrainingTask
from .selectors import (
    manageable_training_tasks_for,
    training_logs_changeable_by,
    training_logs_visible_to,
    visible_task_executions_for,
    visible_training_tasks_for,
)
from .services import build_training_log_archive, record_coach_feedback, update_execution_facts
from .tables import TaskExecutionTable, TrainingCycleTable, TrainingLogTable, TrainingPlanTable, TrainingTaskTable


class ListPageMixin:
    template_name = "training/object_list.html"
    create_url_name = None
    create_label = "新增"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(create_url_name=self.create_url_name, create_label=self.create_label)
        return context


class TrainingCycleListView(ListPageMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = TrainingCycle
    table_class = TrainingCycleTable
    title = "训练周期"
    permission_required = "training.view_trainingcycle"
    create_url_name = "training:cycle_create"
    create_label = "新增训练周期"


class TrainingCycleDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = TrainingCycle
    template_name = "training/cycle_detail.html"
    context_object_name = "cycle"
    title = "{name}"
    permission_required = "training.view_trainingcycle"

    def get_queryset(self):
        return TrainingCycle.objects.select_related("skill_project", "parent").prefetch_related(
            "skill_tree_version_links__technical_domain",
            "skill_tree_version_links__skill_tree_version",
        )


class TrainingCycleCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingCycle
    form_class = TrainingCycleForm
    template_name = "training/cycle_form.html"
    extra_context = {"grid_class": "grid gap-4 md:grid-cols-2"}
    title = "新增训练周期"
    permission_required = "training.add_trainingcycle"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        version_field_names = {name for name, _domain in form.version_fields}
        context["base_fields"] = [
            field for field in form.visible_fields() if field.name not in version_field_names and field.name != "parent"
        ]
        context["parent_field"] = form["parent"]
        context["version_fields"] = [form[name] for name, _domain in form.version_fields]
        return context

    def get_success_url(self):
        return reverse("training:cycle_detail", args=[self.object.pk])


class TrainingCycleUpdateView(TrainingCycleCreateView, UpdateView):
    title = "编辑训练周期"
    permission_required = "training.change_trainingcycle"


@require_GET
def training_cycle_version_fields(request):
    if not (
        request.user.has_perm("training.add_trainingcycle")
        or request.user.has_perm("training.change_trainingcycle")
    ):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    initial = {
        "skill_project": request.GET.get("skill_project"),
        "parent": request.GET.get("parent"),
    }
    preserved = set(filter(None, request.GET.getlist("preserved")))
    for name in preserved:
        initial[name] = request.GET.get(name)
    form = TrainingCycleForm(initial=initial)
    for name, _domain in form.version_fields:
        if name in preserved:
            form.fields[name].widget.attrs["data-cycle-version-touched"] = "true"
    return render(
        request,
        "training/partials/cycle_version_fields.html",
        {
            "parent_field": form["parent"],
            "version_fields": [form[name] for name, _domain in form.version_fields],
        },
    )


class TrainingPlanListView(ListPageMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = TrainingPlan
    table_class = TrainingPlanTable
    title = "训练计划"
    permission_required = "training.view_trainingplan"
    create_url_name = "training:plan_create"
    create_label = "新增训练计划"


class TrainingPlanDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = TrainingPlan
    template_name = "training/plan_detail.html"
    context_object_name = "plan"
    title = "{title}"
    permission_required = "training.view_trainingplan"


class TrainingPlanCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingPlan
    form_class = TrainingPlanForm
    template_name = "common/form.html"
    extra_context = {"grid_class": "grid gap-4 md:grid-cols-2"}
    title = "新增训练计划"
    permission_required = "training.add_trainingplan"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("training:plan_detail", args=[self.object.pk])


class TrainingPlanUpdateView(TrainingPlanCreateView, UpdateView):
    title = "编辑训练计划"
    permission_required = "training.change_trainingplan"


class TrainingTaskListView(ListPageMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = TrainingTask
    table_class = TrainingTaskTable
    title = "训练任务"
    permission_required = "training.view_trainingtask"
    create_url_name = "training:task_create"
    create_label = "新增训练任务"

    def get_queryset(self):
        return visible_training_tasks_for(self.request.user).select_related(
            "training_plan", "training_plan__training_cycle"
        )


class MyTrainingView(TrainingTaskListView):
    title = "我的训练"
    create_url_name = None

    def get_queryset(self):
        return (
            TrainingTask.objects.filter(executions__user=self.request.user).select_related("training_plan").distinct()
        )


class TrainingTaskDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = TrainingTask
    template_name = "training/task_detail.html"
    context_object_name = "task"
    title = "{title}"
    permission_required = "training.view_trainingtask"

    def get_queryset(self):
        return visible_training_tasks_for(self.request.user).prefetch_related(
            "domain_links__technical_domain",
            "skill_links__skill",
            "coach_links__user",
            "executions__user",
            "attachments",
        )


class TrainingTaskCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingTask
    form_class = TrainingTaskForm
    template_name = "common/form.html"
    title = "新增训练任务"
    permission_required = "training.add_trainingtask"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if skill_id := self.request.GET.get("skill"):
            from standards.models import Skill

            skill = Skill.objects.filter(pk=skill_id, is_active=True).first()
            if skill:
                initial.update(
                    skills=[skill],
                    primary_skill=skill,
                    domains=[skill.primary_domain],
                    primary_domain=skill.primary_domain,
                )
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("training:task_detail", args=[self.object.pk])


class TrainingTaskUpdateView(TrainingTaskCreateView, UpdateView):
    title = "编辑训练任务"
    permission_required = "training.change_trainingtask"

    def get_queryset(self):
        return manageable_training_tasks_for(self.request.user)


class TaskExecutionListView(ListPageMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = TaskExecution
    table_class = TaskExecutionTable
    title = "任务执行"
    permission_required = "training.view_taskexecution"
    create_url_name = None

    def get_queryset(self):
        return visible_task_executions_for(self.request.user).select_related("training_task", "user")


class TaskExecutionDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = TaskExecution
    template_name = "training/execution_detail.html"
    context_object_name = "execution"
    title = "任务执行详情"
    permission_required = "training.view_taskexecution"

    def get_queryset(self):
        return visible_task_executions_for(self.request.user)


class TaskExecutionUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = TaskExecution
    form_class = TaskExecutionForm
    template_name = "common/form.html"
    title = "更新任务执行"
    permission_required = "training.change_taskexecution"

    def get_queryset(self):
        return TaskExecution.objects.filter(user=self.request.user)

    def form_valid(self, form):
        self.object = update_execution_facts(self.get_object(), user=self.request.user, **form.cleaned_data)
        return HttpResponse(status=302, headers={"Location": self.get_success_url()})

    def get_success_url(self):
        return reverse("training:execution_detail", args=[self.object.pk])


class CoachFeedbackView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = CoachFeedbackForm
    template_name = "common/form.html"
    title = "填写教练反馈"
    permission_required = "training.change_taskexecution"

    def form_valid(self, form):
        execution = visible_task_executions_for(self.request.user).get(pk=self.kwargs["pk"])
        record_coach_feedback(execution, user=self.request.user, feedback=form.cleaned_data["coach_feedback"])
        messages.success(self.request, "教练反馈已保存。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("training:execution_detail", args=[self.kwargs["pk"]])


class TrainingLogListView(ListPageMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = TrainingLog
    table_class = TrainingLogTable
    title = "训练日志"
    permission_required = "training.view_traininglog"
    create_url_name = "training:log_create"
    create_label = "新增训练日志"

    def get_queryset(self):
        return training_logs_visible_to(self.request.user).select_related("training_cycle", "author")


class TrainingLogDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = TrainingLog
    template_name = "training/log_detail.html"
    context_object_name = "log"
    title = "{topic}"
    permission_required = "training.view_traininglog"

    def get_queryset(self):
        return training_logs_visible_to(self.request.user)


class TrainingLogCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingLog
    form_class = TrainingLogForm
    template_name = "common/form.html"
    title = "新增训练日志"
    permission_required = "training.add_traininglog"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("training:log_detail", args=[self.object.pk])


class TrainingLogUpdateView(TrainingLogCreateView, UpdateView):
    title = "编辑训练日志"
    permission_required = "training.change_traininglog"

    def get_queryset(self):
        return training_logs_changeable_by(self.request.user)


class TrainingLogDownloadView(PermissionRequiredMixin, DetailView):
    model = TrainingLog
    permission_required = "training.view_traininglog"

    def get_queryset(self):
        return training_logs_visible_to(self.request.user).exclude(document="")

    def get(self, request, *args, **kwargs):
        log = self.get_object()
        response = FileResponse(
            log.document.open("rb"),
            as_attachment=True,
            filename=Path(log.document.name).name,
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class TrainingLogArchiveExportView(PermissionRequiredMixin, SingleTableView):
    permission_required = "training.export_traininglog_archive"

    def get(self, request, *args, **kwargs):
        payload = build_training_log_archive(training_logs_visible_to(request.user))
        response = HttpResponse(payload, content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="training-logs.zip"'
        return response
