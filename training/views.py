from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import BooleanField, Count, Exists, F, OuterRef, Q, Value
from pathlib import Path

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.decorators.http import require_GET
from django.views.decorators.vary import vary_on_headers
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DeleteView, DetailView, FormView, TemplateView, UpdateView
from django_tables2 import SingleTableView
from django.http import QueryDict
from django import forms
from django.contrib.auth import get_user_model
from accounts.services.user_management import filter_users, normalize_ids
from accounts.user_management_forms import UserFilterForm
from core.utils.listing import FilterableListMixin, ListFilterSpec
from .member_tables import CycleCandidateTable, CycleMemberTable
from .member_management import MemberActionForm, prepare_member_add, preview_member_add, confirm_member_add, load_member_add
from .log_management import (
    LogFilterForm, LogDeleteActionForm, filter_training_logs, can_manage_log_deletions,
    preview_log_deletion, confirm_log_deletion, delete_training_logs, log_list_return_url,
)

from core.utils.breadcrumbs import breadcrumb_link
from core.utils.mixins import TitleMixin
from accounts.services.users import get_user_display_name
from core.file_preview import (
    FilePreviewMetadata, build_file_preview_descriptor, build_inline_preview_response, build_download_response,
)

from .forms import (
    CoachFeedbackForm,
    CycleMemberAddForm,
    CycleMemberEditForm,
    TaskExecutionForm,
    TrainingCycleForm,
    TrainingCycleTreeVersionsForm,
    TrainingLogForm,
    TrainingLogStatisticsForm,
    TrainingPlanForm,
    TrainingTaskForm,
)
from .models import TaskExecution, TrainingCycle, TrainingCycleMember, TrainingLog, TrainingPlan, TrainingTask
from .selectors import (
    log_plan_choices,
    log_plan_is_ongoing,
    manageable_training_tasks_for,
    training_logs_changeable_by,
    training_logs_deletable_by,
    training_logs_visible_to,
    training_log_submission_statistics,
    training_log_statistics_plans_for,
    visible_task_executions_for,
    visible_training_tasks_for,
)
from .services import (
    build_training_log_archive, record_coach_feedback, update_execution_facts, save_cycle_member, remove_cycle_member,
)
from .tables import TaskExecutionTable, TrainingCycleTable, TrainingLogTable, TrainingPlanTable, TrainingTaskTable


class ListPageMixin:
    template_name = "training/object_list.html"
    create_url_name = None
    create_label = "新增"
    create_permission = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        permission = self.create_permission or (f"{self.model._meta.app_label}.add_{self.model._meta.model_name}" if self.model else None)
        context.update(create_url_name=self.create_url_name if permission and self.request.user.has_perm(permission) else None, create_label=self.create_label)
        return context


class TrainingCycleListView(FilterableListMixin, ListPageMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = TrainingCycle
    table_class = TrainingCycleTable
    template_name = "training/cycle_list.html"
    title = "训练周期"
    permission_required = "training.view_trainingcycle"
    create_url_name = "training:cycle_create"
    create_label = "新增训练周期"
    table_pagination = {"per_page": 25}
    search_fields = ("code", "name", "skill_project__name")
    list_filter_specs = (
        ListFilterSpec("q", "搜索训练周期", "search", placeholder="搜索周期代码、名称或技能项目"),
        ListFilterSpec("status", "状态", "select", lookup="status", choices=TrainingCycle.Status.choices,
                       empty_label="全部状态"),
    )

    def get_base_queryset(self):
        return super().get_base_queryset().select_related("skill_project")


class TrainingCycleDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = TrainingCycle
    template_name = "training/cycle_detail.html"
    context_object_name = "cycle"
    title = "{name}"
    permission_required = "training.view_trainingcycle"

    def get_breadcrumb_parents(self):
        if not self.request.user.has_perm("training.view_trainingcycle"):
            return []
        return [breadcrumb_link("训练周期", "training:cycle_list")]

    def get_queryset(self):
        return TrainingCycle.objects.select_related("skill_project", "parent").prefetch_related(
            "skill_tree_version_links__technical_domain",
            "skill_tree_version_links__skill_tree_version",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tree_versions_locked"] = not self.object.can_add_skill_tree_bindings
        context["tree_versions_append_only"] = self.object.status == TrainingCycle.Status.ACTIVE
        if self.request.user.has_perm("training.change_trainingcycle") and "cycle_form" not in context:
            context["cycle_form"] = TrainingCycleForm(instance=self.object)
        if self.request.user.has_perm("training.view_trainingcyclemember"):
            members = self.object.members.select_related("user").order_by("user__last_name", "user__first_name", "pk")
            context["members_page"] = Paginator(members, 25).get_page(self.request.GET.get("members_page"))
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("training.change_trainingcycle"):
            raise PermissionDenied
        # 保存时不要沿用详情页预取的快照，状态校验需要读取锁定后的最新关系。
        self.object = self.get_object(queryset=self.get_queryset().prefetch_related(None))
        form = TrainingCycleForm(request.POST, instance=self.object)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as exc:
                form.add_error(None, "；".join(exc.messages))
            else:
                messages.success(request, "已保存训练周期信息。")
                return redirect(request.get_full_path())
        # ModelForm 校验会修改内存中的实例；其他区块必须继续展示已保存的数据。
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data(cycle_form=form))


class TrainingCycleMembersView(FilterableListMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    template_name = "training/cycle_members.html"
    title = "周期成员管理"
    title_icon = "icon-[tabler--users]"
    permission_required = "training.view_trainingcyclemember"
    table_pagination = {"per_page": 25}
    model = get_user_model()

    def dispatch(self, request, *args, **kwargs):
        self.cycle = get_object_or_404(TrainingCycle, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_breadcrumb_parents(self):
        if self.request.user.has_perm("training.view_trainingcycle"):
            return [breadcrumb_link("训练周期", "training:cycle_list"),
                    breadcrumb_link(self.cycle.name, "training:cycle_detail", args=[self.cycle.pk])]
        return []

    @property
    def adding(self):
        return self.request.GET.get("mode") == "add"

    def get_list_filter_specs(self):
        specs = [ListFilterSpec("mode", "成员列表", "select", choices=[("add", "添加成员")], empty_label="已有成员"),
                 ListFilterSpec("q", "搜索用户", "search", placeholder="姓名、拼音或学号"),
                 ListFilterSpec("role", "用户角色", "select", choices=UserFilterForm().fields["role"].choices[1:],
                                empty_label="全部用户角色")]
        if not self.request.user.has_perm("training.add_trainingcyclemember"):
            specs = specs[1:]
        if not self.adding:
            specs += [ListFilterSpec("member_role", "周期身份", "select", choices=TrainingCycleMember.Role.choices,
                                    empty_label="全部周期身份"),
                      ListFilterSpec("current", "当前周期", "select", choices=[("1", "是"), ("0", "否")],
                                     empty_label="全部当前状态")]
        return specs

    def get_queryset(self):
        filters = UserFilterForm(self.request.GET)
        if not filters.is_valid() or self.request.GET.get("mode", "") not in ("", "add"):
            raise ValidationError("筛选条件无效，请重新选择。")
        queryset = self.model.objects.select_related("profile").prefetch_related("groups")
        if self.adding:
            if not self.request.user.has_perm("training.add_trainingcyclemember"):
                raise PermissionDenied
            queryset = queryset.filter(is_active=True).exclude(training_cycle_memberships__training_cycle=self.cycle)
        else:
            queryset = queryset.filter(training_cycle_memberships__training_cycle=self.cycle).annotate(
                member_pk=F("training_cycle_memberships__pk"),
                member_cycle_id=F("training_cycle_memberships__training_cycle_id"),
                member_role=F("training_cycle_memberships__role"),
                member_current=F("training_cycle_memberships__is_current"),
            )
            role, current = self.request.GET.get("member_role", ""), self.request.GET.get("current", "")
            if role not in ("", *TrainingCycleMember.Role.values) or current not in ("", "0", "1"):
                raise ValidationError("筛选条件无效，请重新选择。")
            if role:
                queryset = queryset.filter(member_role=role)
            if current:
                queryset = queryset.filter(member_current=current == "1")
        return filter_users(queryset, filters.cleaned_data).order_by(F("profile__join_date").desc(nulls_last=True), "-pk")

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except ValidationError as exc:
            return HttpResponse("；".join(exc.messages), status=400)

    def get_table_class(self):
        return CycleCandidateTable if self.adding else CycleMemberTable

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(cycle=self.cycle, adding=self.adding, action_form=MemberActionForm())
        return context

    def return_url(self, query):
        allowed = {"mode", "q", "role", "member_role", "current", "sort", "page"}
        params = QueryDict(query).copy()
        for key in list(params):
            if key not in allowed:
                del params[key]
        return self.request.path + ("?" + params.urlencode() if params else "")

    def render_step(self, template, context):
        from core.utils.breadcrumbs import build_breadcrumbs

        context.update(title=self.get_title(), title_icon=self.title_icon,
                       breadcrumbs=build_breadcrumbs(self.request, self.get_title(), self.get_breadcrumb_parents()))
        return render(self.request, template, context)

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("training.add_trainingcyclemember"):
            raise PermissionDenied
        stage = request.POST.get("stage", "select")
        try:
            if stage == "confirm":
                query = confirm_member_add(actor=request.user, cycle=self.cycle, token=request.POST.get("token", ""))
                messages.success(request, "已添加周期成员。")
                return redirect(self.return_url(query))
            if stage == "select":
                action = MemberActionForm(request.POST)
                if request.POST.get("selection") != "selected" or not action.is_valid() or not self.adding:
                    raise ValidationError("请选择有效操作和当前页成员。")
                self.object_list = self.get_queryset()
                table = self.get_table()
                ids = normalize_ids(request.POST.getlist("users"))
                page_ids = {row.record.pk for row in table.page.object_list}
                if not set(ids) <= page_ids:
                    raise ValidationError("所选用户不属于当前筛选页，请重新选择。")
                state = prepare_member_add(actor=request.user, cycle=self.cycle, ids=ids,
                                           return_query=request.GET.urlencode())
                form = CycleMemberAddForm(initial={"users": ids})
            elif stage == "parameters":
                token = request.POST.get("token", "")
                data, users = load_member_add(actor=request.user, cycle=self.cycle, token=token, stage="parameters")
                bound = request.POST.copy()
                bound.setlist("users", [str(pk) for pk in data["ids"]])
                form = CycleMemberAddForm(bound)
                state = {"token": token, "users": users, "return_query": data["return_query"]}
            else:
                raise ValidationError("操作步骤无效。")
            form.fields["users"].widget = forms.MultipleHiddenInput()
            if not request.user.has_perm("training.change_trainingcyclemember"):
                form.fields.pop("is_current")
            if stage == "parameters" and form.is_valid():
                try:
                    preview = preview_member_add(actor=request.user, cycle=self.cycle, token=state["token"],
                                                 role=form.cleaned_data["role"],
                                                 is_current=form.cleaned_data.get("is_current", False))
                except ValidationError as exc:
                    form.add_error(None, "；".join(exc.messages))
                else:
                    return self.render_step("training/member_add_confirm.html", {
                        "cycle": self.cycle, **preview, "return_url": self.return_url(preview["return_query"]),
                    })
            return self.render_step("training/member_add_parameters.html", {
                "cycle": self.cycle, "form": form, **state,
                "return_url": self.return_url(state["return_query"]),
            })
        except ValidationError as exc:
            messages.error(request, "；".join(exc.messages))
            return redirect(self.return_url(request.GET.urlencode()))


class TrainingCycleMemberEditView(TitleMixin, PermissionRequiredMixin, FormView):
    template_name = "training/member_form.html"
    form_class = CycleMemberEditForm
    title = "维护周期成员"
    permission_required = ("training.view_trainingcyclemember", "training.change_trainingcyclemember")

    def dispatch(self, request, *args, **kwargs):
        self.member = get_object_or_404(
            TrainingCycleMember.objects.select_related("user", "training_cycle"),
            pk=kwargs["member_pk"], training_cycle_id=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_breadcrumb_parents(self):
        return [breadcrumb_link("周期成员管理", "training:cycle_members", args=[self.member.training_cycle_id])]

    def get_initial(self):
        return {"role": self.member.role, "is_current": self.member.is_current}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["member"] = self.member
        context["removal_error"] = self.member.removal_error()
        return context

    def form_valid(self, form):
        self.member.role = form.cleaned_data["role"]
        self.member.is_current = form.cleaned_data["is_current"]
        try:
            save_cycle_member(self.member)
        except ValidationError as exc:
            form.add_error(None, "；".join(exc.messages))
            return self.form_invalid(form)
        messages.success(self.request, "已保存周期成员。")
        return redirect("training:cycle_members", pk=self.member.training_cycle_id)


class TrainingCycleMemberDeleteView(TrainingCycleMemberEditView):
    template_name = "training/member_confirm_delete.html"
    title = "移除周期成员"
    permission_required = ("training.view_trainingcyclemember", "training.delete_trainingcyclemember")

    def post(self, request, *args, **kwargs):
        try:
            remove_cycle_member(self.member)
        except ValidationError as exc:
            messages.error(request, "；".join(exc.messages))
        else:
            messages.success(request, "已移除周期成员。")
        return redirect("training:cycle_members", pk=self.member.training_cycle_id)


class TrainingCycleCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingCycle
    form_class = TrainingCycleForm
    template_name = "training/cycle_form.html"
    extra_context = {"grid_class": "grid gap-4 md:grid-cols-2"}
    title = "新增训练周期"
    permission_required = "training.add_trainingcycle"

    def get_breadcrumb_parents(self):
        if not self.request.user.has_perm("training.view_trainingcycle"):
            return []
        return [breadcrumb_link("训练周期", "training:cycle_list")]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        context["base_fields"] = [field for field in form.visible_fields() if field.name != "parent"]
        context["parent_field"] = form["parent"]
        return context

    def form_valid(self, form):
        try:
            self.object = form.save()
        except ValidationError as exc:
            form.add_error(None, "；".join(exc.messages))
            return self.form_invalid(form)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("training:cycle_detail", args=[self.object.pk])


class TrainingCycleUpdateView(TrainingCycleCreateView, UpdateView):
    title = "编辑训练周期"
    permission_required = "training.change_trainingcycle"


class TrainingCycleTreeVersionsUpdateView(TitleMixin, PermissionRequiredMixin, FormView):
    template_name = "training/cycle_tree_versions_form.html"
    form_class = TrainingCycleTreeVersionsForm
    title = "编辑领域技能树版本快照"
    permission_required = "training.change_trainingcycle"

    def dispatch(self, request, *args, **kwargs):
        self.cycle = get_object_or_404(TrainingCycle.objects.select_related("skill_project", "parent"), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_breadcrumb_parents(self):
        if not self.request.user.has_perm("training.view_trainingcycle"):
            return []
        return [breadcrumb_link("训练周期", "training:cycle_list"),
                breadcrumb_link(self.cycle.name, "training:cycle_detail", args=[self.cycle.pk])]

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "cycle": self.cycle}

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "cycle": self.cycle,
                "tree_versions_locked": not self.cycle.can_add_skill_tree_bindings,
                "tree_versions_append_only": self.cycle.status == TrainingCycle.Status.ACTIVE}

    def form_valid(self, form):
        try:
            form.save()
        except ValidationError as exc:
            form.add_error(None, "；".join(exc.messages))
            return self.form_invalid(form)
        messages.success(self.request, "已保存领域技能树版本快照。")
        return redirect("training:cycle_detail", pk=self.cycle.pk)


@require_GET
def training_cycle_parent_field(request):
    if not (
        request.user.has_perm("training.add_trainingcycle")
        or request.user.has_perm("training.change_trainingcycle")
    ):
        raise PermissionDenied
    cycle_id = request.GET.get("cycle_id", "")
    cycle = get_object_or_404(TrainingCycle, pk=cycle_id) if cycle_id.isdigit() else None
    form = TrainingCycleForm(data=request.GET, instance=cycle)
    return render(request, "training/partials/cycle_parent_field.html", {"parent_field": form["parent"]})


class TrainingPlanListView(FilterableListMixin, ListPageMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    template_name = "training/plan_list.html"
    model = TrainingPlan
    table_class = TrainingPlanTable
    title = "训练计划"
    permission_required = "training.view_trainingplan"
    create_url_name = "training:plan_create"
    create_label = "新增训练计划"
    table_pagination = {"per_page": 25}
    search_fields = ("title", "training_cycle__code", "training_cycle__name")
    status_filter = ListFilterSpec(
        "status", "状态", "select",
        choices=(("unpublished", "未发布"), ("published", "已发布"), ("completed", "已完成")),
        empty_label="全部状态",
    )
    list_filter_specs = (
        ListFilterSpec("q", "搜索训练计划", "search", placeholder="搜索计划标题或周期代码、名称"),
        status_filter,
    )

    def get_base_queryset(self):
        from .scheduling import visible_plans
        queryset = visible_plans(self.request.user).select_related("training_cycle")
        if self.request.user.is_active and self.request.user.is_superuser:
            return queryset.annotate(can_edit=Value(True, output_field=BooleanField()))
        # 与 plan_manager 的创建人／排班人员范围一致，避免逐行查询。
        scope = Q(created_by=self.request.user)
        if self.request.user.has_perm("training.schedule_trainingplan"):
            scope |= Q(schedulers=self.request.user)
        manageable = TrainingPlan.objects.filter(pk=OuterRef("pk")).filter(scope)
        return queryset.annotate(can_edit=Exists(manageable) if self.request.user.has_perm("training.change_trainingplan") else Value(False, output_field=BooleanField()))

    def apply_custom_filters(self, queryset):
        status = self.get_filter_value(self.status_filter)
        if not status:
            return queryset
        # 与 TrainingPlan.display_status 一致：结束日期过后优先显示已完成。
        today = timezone.localdate()
        if status == "completed":
            return queryset.filter(end_date__lt=today)
        if status in {"unpublished", "published"}:
            return queryset.filter(end_date__gte=today, published_at__isnull=status == "unpublished")
        return queryset


class MyTrainingPlanListView(TrainingPlanListView):
    title = "我的计划"
    create_url_name = None
    status_filter = ListFilterSpec(
        "status", "状态", "select",
        choices=TrainingPlanListView.status_filter.choices,
        empty_label="进行中及即将开始",
    )
    list_filter_specs = (TrainingPlanListView.list_filter_specs[0], status_filter)

    def get_base_queryset(self):
        from .scheduling import my_plans

        return my_plans(super().get_base_queryset(), self.request.user)

    def apply_custom_filters(self, queryset):
        if not self.get_filter_value(self.status_filter):
            return queryset.filter(end_date__gte=timezone.localdate())
        return super().apply_custom_filters(queryset)


class TrainingPlanDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = TrainingPlan
    template_name = "training/plan_detail.html"
    context_object_name = "plan"
    title = "{title}"
    permission_required = "training.view_trainingplan"

    def get_breadcrumb_parents(self):
        if not self.request.user.has_perm("training.view_trainingplan"):
            return []
        return [breadcrumb_link("训练计划", "training:plan_list")]


class TrainingPlanCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingPlan
    form_class = TrainingPlanForm
    template_name = "training/plan_form.html"
    extra_context = {"publish_button": True}
    title = "新增训练计划"
    permission_required = "training.add_trainingplan"

    def get_initial(self):
        initial = super().get_initial()
        if self.object is None:
            if not self.request.user.is_superuser and self.request.user.has_perm("training.schedule_trainingplan"):
                initial["schedulers"] = [self.request.user.pk]
            cycle_id = TrainingCycleMember.objects.filter(
                user=self.request.user, is_current=True
            ).values_list("training_cycle_id", flat=True).first()
            if cycle_id is not None:
                initial["training_cycle"] = cycle_id
        return initial

    def get_breadcrumb_parents(self):
        if not self.request.user.has_perm("training.view_trainingplan"):
            return []
        return [breadcrumb_link("训练计划", "training:plan_list")]

    def form_valid(self, form):
        from .scheduling import save_plan_definition
        try:
            self.object = save_plan_definition(form, self.request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "计划已保存。")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("training:plan_detail", args=[self.object.pk])


class TrainingPlanUpdateView(TrainingPlanCreateView, UpdateView):
    title = "编辑训练计划"
    permission_required = "training.change_trainingplan"

    def get_queryset(self):
        from .scheduling import visible_plans
        return visible_plans(self.request.user)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        from .scheduling import plan_manager
        if not plan_manager(self.request.user, obj):
            raise PermissionDenied
        return obj


class TrainingTaskListView(ListPageMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = TrainingTask
    table_class = TrainingTaskTable
    title = "训练任务"
    permission_required = "training.view_trainingtask"
    create_url_name = "training:task_create"
    create_label = "新增训练任务"

    def get_queryset(self):
        from django.db.models import Exists, OuterRef
        from .scheduling import ACTIVE_KINDS
        return visible_training_tasks_for(self.request.user).annotate(
            can_edit=Exists(manageable_training_tasks_for(self.request.user).filter(
                pk=OuterRef("pk"), schedule_slot__isnull=False,
                schedule_slot__kind__in=ACTIVE_KINDS,
            ).exclude(status="cancelled"))
        ).select_related(
            "training_plan", "training_plan__training_cycle"
        )


class TrainingTaskDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = TrainingTask
    template_name = "training/task_detail.html"
    context_object_name = "task"
    title = "{title}"
    permission_required = "training.view_trainingtask"

    def get_context_data(self, **kwargs):
        from .scheduling import can_fill, task_manager
        task, user = self.object, self.request.user
        can_edit = bool(task.schedule_slot_id and can_fill(user, task.schedule_slot))
        can_skills = can_fill(user, task.schedule_slot, skills_only=True) if task.schedule_slot_id else task_manager(user, task.training_plan) and user.has_perm("training.change_trainingtask")
        executions = visible_task_executions_for(user).filter(training_task=task).select_related("user")
        if not user.has_perm("training.view_taskexecution"):
            executions = executions.none()
        from .schedule_history import decorate_history
        from .scheduling import staff
        from django.db.models import Q
        history = task.training_plan.change_records.filter(
            Q(task=task) | Q(task__isnull=True, action__in=["批准排班调整", "批准调整"])
        ).select_related("actor")
        if not staff(user, task.training_plan) and not task.coach_links.filter(user=user).exists():
            history = history.none()
        history = [record for record in history[:100] if record.task_id == task.pk or any(
            (change["type"] == "slot" and change.get("id") == task.schedule_slot_id)
            or (change["type"] == "day" and task.schedule_slot_id and change.get("id") == task.schedule_slot.day_id)
            or (change["type"] == "swap" and task.schedule_slot_id in change["slots"])
            or (change["type"] == "task" and change.get("id") == task.pk)
            or change["type"] == "times"
            for change in record.after.get("调整", [])
        )]
        history, _ = decorate_history(history)
        from .process_views import markdown
        return super().get_context_data(can_edit=can_edit, can_skills=can_skills, visible_executions=executions, task_history=history, description_html=markdown(task.description), **kwargs)

    def get_breadcrumb_parents(self):
        if not self.request.user.has_perm("training.view_trainingtask"):
            return []
        return [breadcrumb_link("训练计划", "training:plan_list"), breadcrumb_link(self.object.training_plan.title, "training:plan_detail", args=[self.object.training_plan_id])]

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

    def get_breadcrumb_parents(self):
        if not self.request.user.has_perm("training.view_trainingtask"):
            return []
        return [breadcrumb_link("训练任务", "training:task_list")]

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
        from django.db.models import Q
        return visible_task_executions_for(self.request.user).annotate(can_edit=Q(user=self.request.user)).select_related("training_task", "user")


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
        return visible_task_executions_for(self.request.user).filter(user=self.request.user)

    def form_valid(self, form):
        try:
            self.object = update_execution_facts(self.get_object(), user=self.request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
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


@method_decorator(vary_on_headers("HX-Request"), name="dispatch")
class TrainingLogMonthlyStatView(FilterableListMixin, TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "training/monthly_stats.html"
    title = "训练日志提交统计"
    title_icon = "icon-[tabler--chart-bar]"
    permission_required = "training.view_traininglog_statistics"
    list_filter_compact = True

    @cached_property
    def plans(self):
        return training_log_statistics_plans_for(self.request.user).order_by("-start_date", "-pk")

    def get_list_filter_specs(self):
        today = timezone.localdate()
        return (
            ListFilterSpec("q", "搜索人员", "search", placeholder="姓名、全拼或首字母"),
            ListFilterSpec(
                "plan", "训练计划", "select", empty_label="自动选择进行中的计划",
                choices=log_plan_choices(self.plans, today),
            ),
            ListFilterSpec("date_from", "训练日期从", "date", placeholder="从"),
            ListFilterSpec("date_to", "训练日期至", "date", placeholder="至"),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        form = TrainingLogStatisticsForm(self.request.GET, plans=self.plans)
        context.update(form=form, has_plans=bool(self.plans), can_view_log=user.has_perm("training.view_traininglog"))
        if form.is_valid():
            filters = form.cleaned_data
            selected = filters["plan"] or next(
                (plan for plan in self.plans if log_plan_is_ongoing(plan, timezone.localdate())), None,
            )
            if selected:
                from .daily_progress import training_day_is_available, training_day_url

                context.update(
                    training_log_submission_statistics(user, **{**filters, "plan": selected}),
                    selected_plan=selected,
                )
                if user.has_perms(("training.add_traininglog", "training.view_taskexecution", "training.view_trainingprogress")):
                    member = selected.training_cycle.members.filter(user=user).select_related("training_cycle").first()
                    today = timezone.localdate()
                    for row in context.get("rows", []):
                        if (row["own_missing_competitor"] is not None or row["own_missing_coach"] is not None
                                ) and training_day_is_available(member, row["date"], today):
                            row["write_url"] = training_day_url("training:log_ai_start", selected.training_cycle_id, row["date"])
        return context


class TrainingLogListView(FilterableListMixin, ListPageMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = TrainingLog
    table_class = TrainingLogTable
    title = "训练日志"
    permission_required = "training.view_traininglog"
    create_url_name = "training:log_create"
    create_label = "上传训练日志"
    template_name = "training/log_list.html"
    title_icon = "icon-[tabler--notebook]"
    table_pagination = {"per_page": 25}
    list_filter_compact = True

    @cached_property
    def filter_form(self):
        return LogFilterForm(self.request.GET, user=self.request.user)

    def get_list_filter_specs(self):
        return (
            ListFilterSpec("q", "搜索日志", "search", placeholder="姓名、拼音、学号、主题、摘要或文件名"),
            ListFilterSpec("plan", "训练计划", "select",
                           choices=self.filter_form.fields["plan"].choices[1:],
                           empty_label=self.filter_form.fields["plan"].choices[0][1]),
            ListFilterSpec("date_from", "训练日期从", "date", placeholder="从"),
            ListFilterSpec("date_to", "训练日期至", "date", placeholder="至"),
            ListFilterSpec("member_role", "周期身份", "select", choices=TrainingCycleMember.Role.choices,
                           empty_label="全部周期身份"),
        )

    def get_queryset(self):
        user = self.request.user
        queryset = filter_training_logs(user, self.request.GET, form=self.filter_form) if self.filter_form.is_valid() else TrainingLog.objects.none()
        return (
            queryset
            .select_related("training_cycle", "author")
            .annotate(
                execution_count=Count("executions"),
                can_edit=Exists(training_logs_changeable_by(user).filter(pk=OuterRef("pk"))),
                can_delete=Exists(training_logs_deletable_by(user).filter(pk=OuterRef("pk"))),
            )
        )

    @cached_property
    def can_bulk_delete(self):
        return can_manage_log_deletions(self.request.user) and self.object_list.filter(can_delete=True).exists()

    def get_table_kwargs(self):
        return {"can_bulk_delete": self.can_bulk_delete}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            filter_form=self.filter_form, bulk_form=LogDeleteActionForm(), can_bulk_delete=self.can_bulk_delete,
            no_current_plan=self.filter_form.is_valid() and not self.filter_form.cleaned_data["plan"]
            and self.filter_form.default_plan is None,
        )
        return context

    def post(self, request, *args, **kwargs):
        if not can_manage_log_deletions(request.user):
            raise PermissionDenied
        try:
            if request.POST.get("stage", "preview") == "confirm":
                query = confirm_log_deletion(actor=request.user, token=request.POST.get("token", ""))
                messages.success(request, "已删除所选训练日志及其文件。")
                return redirect(log_list_return_url(query))
            action = LogDeleteActionForm(request.POST)
            if request.POST.get("stage", "preview") != "preview" or request.POST.get("selection") != "selected" or not action.is_valid():
                raise ValidationError("请选择有效的批量操作和日志。")
            if not self.filter_form.is_valid():
                raise ValidationError("筛选条件无效，请返回列表重新筛选。")
            self.object_list = self.get_queryset()
            table = self.get_table(**self.get_table_kwargs())
            ids = normalize_ids(request.POST.getlist("logs"))
            if not set(ids) <= {row.record.pk for row in table.page.object_list if row.record.can_delete}:
                raise ValidationError("部分日志不在当前筛选页或不可删除，请重新选择。")
            preview = preview_log_deletion(actor=request.user, ids=ids, return_query=request.GET.urlencode())
            from core.utils.breadcrumbs import build_breadcrumbs

            title = "确认批量删除训练日志"
            return render(request, "training/log_bulk_delete.html", {
                **preview, "title": title, "title_icon": self.title_icon,
                "breadcrumbs": build_breadcrumbs(request, title, [breadcrumb_link("训练日志", "training:log_list")]),
                "return_url": log_list_return_url(preview["return_query"]),
            })
        except ValidationError as exc:
            messages.error(request, "；".join(exc.messages))
            return redirect(log_list_return_url(request.GET.urlencode()))


class TrainingLogDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = TrainingLog
    template_name = "training/log_detail.html"
    context_object_name = "log"
    title = "{topic}"
    permission_required = "training.view_traininglog"

    def get_breadcrumb_parents(self):
        if not self.request.user.has_perm("training.view_traininglog"):
            return []
        return [breadcrumb_link("训练日志", "training:log_list")]

    def get_queryset(self):
        return training_logs_visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log = self.object
        user = self.request.user
        context["can_edit"] = user.has_perm("training.change_traininglog") and (
            training_logs_changeable_by(user).filter(pk=log.pk).exists()
        )
        context["can_delete"] = training_logs_deletable_by(user).filter(pk=log.pk).exists()
        context["file_preview"] = build_file_preview_descriptor(
            file=log.document,
            filename=Path(log.document.name).name if log.document else "尚未上传日志文件",
            download_url=reverse("training:log_download", args=[log.pk]),
            preview_url=reverse("training:log_preview", args=[log.pk]),
            uploader_name=get_user_display_name(log.author), uploaded_at=log.created_at,
            source_label="训练日志", source_url=reverse("training:log_list"),
            title=log.topic, description=log.summary,
            metadata=(FilePreviewMetadata("训练周期", log.training_cycle.name),
                      FilePreviewMetadata("训练日期", log.training_date.strftime("%Y-%m-%d"), is_date=True)),
        )
        return context


class TrainingLogCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingLog
    form_class = TrainingLogForm
    template_name = "training/log_form.html"
    title = "上传当天训练日志"
    permission_required = "training.add_traininglog"
    backfill = False

    def get_form(self, form_class=None):
        from .log_template_views import configure_log_template_form

        form = super().get_form(form_class)
        if not self.object and not form.fixed_day:
            configure_log_template_form(form, backfill=self.backfill)
        return form

    def get_context_data(self, **kwargs):
        from .log_template_views import log_template_context

        context = super().get_context_data(**kwargs)
        if not self.object:
            form = context["form"]
            context.update(log_template_context(self.request.user, form["training_cycle"].value(),
                                                backfill=self.backfill))
            context["show_log_templates"] = True
            if form.fixed_day:
                context["training_return_url"] = (
                    f"{reverse('training:my_training')}?date={form.fixed_day[1].isoformat()}"
                )
        return context

    def get_breadcrumb_parents(self):
        if not self.request.user.has_perm("training.view_traininglog"):
            return []
        return [breadcrumb_link("训练日志", "training:log_list")]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["author"] = self.request.user
        kwargs["backfill"] = self.backfill
        kwargs["simplified_upload"] = self.object is None
        if self.object is None and ("cycle" in self.request.GET or "training_date" in self.request.GET):
            from .log_ai_forms import TrainingDayForm

            selection = TrainingDayForm(self.request.GET, user=self.request.user)
            if not selection.is_valid():
                raise Http404("无效的训练日志日期或周期。")
            cycle, day = selection.cleaned_data["cycle"], selection.cleaned_data["training_date"]
            if self.backfill != (day < timezone.localdate()):
                raise Http404("所选日期不适用于此上传入口。")
            kwargs["fixed_day"] = (cycle, day)
        return kwargs

    def get_success_url(self):
        return reverse("training:log_detail", args=[self.object.pk])

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)


class TrainingLogBackfillView(TrainingLogCreateView):
    title = "补交历史训练日志"
    backfill = True


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
        return build_download_response(log.document, Path(log.document.name or "").name)


class TrainingLogPreviewView(TrainingLogDownloadView):
    def get(self, request, *args, **kwargs):
        log = self.get_object()
        return build_inline_preview_response(log.document, Path(log.document.name or "").name)


class TrainingLogDeleteView(TitleMixin, PermissionRequiredMixin, DeleteView):
    http_method_names = ["get", "post", "head", "options"]
    model = TrainingLog
    template_name = "training/log_confirm_delete.html"
    title = "删除训练日志"
    permission_required = ("training.view_traininglog", "training.delete_traininglog")

    def get_queryset(self):
        return training_logs_deletable_by(self.request.user)

    def get_success_url(self):
        return log_list_return_url(self.request.GET.get("return_query", ""))

    def form_valid(self, form):
        try:
            delete_training_logs(actor=self.request.user, ids=[self.object.pk])
        except ValidationError as exc:
            messages.error(self.request, "；".join(exc.messages))
        else:
            messages.success(self.request, "已删除训练日志及其附件。")
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = (
            self.get_success_url() if "return_query" in self.request.GET
            else reverse("training:log_detail", args=[self.object.pk])
        )
        return context


class TrainingLogArchiveExportView(PermissionRequiredMixin, SingleTableView):
    permission_required = "training.export_traininglog_archive"

    def get(self, request, *args, **kwargs):
        payload = build_training_log_archive(training_logs_visible_to(request.user))
        response = HttpResponse(payload, content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="training-logs.zip"'
        return response
