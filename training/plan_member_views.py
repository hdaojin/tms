"""计划参与选手列表、添加和退出确认页面。"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import F
from django.http import HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_tables2 import SingleTableView

from accounts.services.user_management import filter_users, normalize_ids
from accounts.user_management_forms import UserFilterForm
from core.utils.breadcrumbs import breadcrumb_link, build_breadcrumbs
from core.utils.listing import FilterableListMixin, ListFilterSpec
from core.utils.mixins import TitleMixin

from .member_tables import CycleCandidateTable, PlanMemberTable
from .models import TrainingPlanParticipant
from .plan_members import PlanMemberActionForm, candidates, confirm_members, preview_members, require_manager
from .scheduling import visible_plans


class PlanMembersView(FilterableListMixin, TitleMixin, SingleTableView):
    template_name = "training/plan_members.html"
    title = "计划成员管理"
    title_icon = "icon-[tabler--users]"
    model = get_user_model()
    table_pagination = {"per_page": 25}

    def dispatch(self, request, *args, **kwargs):
        self.plan = get_object_or_404(visible_plans(request.user), pk=kwargs["pk"])
        require_manager(request.user, self.plan)
        return super().dispatch(request, *args, **kwargs)

    @property
    def adding(self):
        return self.request.GET.get("mode") == "add"

    def get_breadcrumb_parents(self):
        return [breadcrumb_link("训练计划", "training:plan_list"),
                breadcrumb_link(self.plan.title, "training:plan_detail", args=[self.plan.pk])]

    def get_list_filter_specs(self):
        specs = [
            ListFilterSpec("mode", "成员列表", "select", choices=[("add", "添加成员")], empty_label="已有成员"),
            ListFilterSpec("q", "搜索用户", "search", placeholder="账号、完整姓名或学号"),
            ListFilterSpec("role", "用户角色", "select", choices=UserFilterForm().fields["role"].choices[1:],
                           empty_label="全部用户角色"),
        ]
        if not self.adding:
            specs.append(ListFilterSpec("participation", "参与状态", "select", choices=[("0", "已退出"), ("all", "全部")],
                                        empty_label="参与中"))
        return specs

    def get_queryset(self):
        filters = UserFilterForm({key: self.request.GET.get(key, "") for key in ("q", "role")})
        if (not filters.is_valid() or self.request.GET.get("mode", "") not in ("", "add")
                or self.request.GET.get("participation", "") not in ("", "0", "all")):
            raise ValidationError("筛选条件无效，请重新选择。")
        if self.adding:
            queryset = candidates(self.plan)
        else:
            queryset = self.model.objects.filter(training_plan_participations__training_plan=self.plan).annotate(
                participant_id=F("training_plan_participations__pk"),
                participant_plan_id=F("training_plan_participations__training_plan_id"),
                participating=F("training_plan_participations__is_active"),
            )
            if self.request.GET.get("participation") != "all":
                queryset = queryset.filter(participating=self.request.GET.get("participation") != "0")
        queryset = queryset.select_related("profile").prefetch_related("groups")
        return filter_users(queryset, filters.cleaned_data).order_by(F("profile__join_date").desc(nulls_last=True), "-pk")

    def get_table_class(self):
        return CycleCandidateTable if self.adding else PlanMemberTable

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(plan=self.plan, adding=self.adding, action_form=PlanMemberActionForm())
        return context

    def return_url(self, query):
        params = QueryDict(query).copy()
        for key in list(params):
            if key not in {"mode", "q", "role", "participation", "sort", "page"}:
                del params[key]
        return reverse("training:plan_members", args=[self.plan.pk]) + ("?" + params.urlencode() if params else "")

    def confirmation(self, preview):
        return render(self.request, "training/plan_member_confirm.html", {
            "plan": self.plan, **preview, "return_url": self.return_url(preview["return_query"]),
            "title": "确认添加计划成员" if preview["operation"] == "add" else "确认退出计划成员",
            "title_icon": self.title_icon,
            "breadcrumbs": build_breadcrumbs(self.request, self.title, [
                *self.get_breadcrumb_parents(), breadcrumb_link(self.title, "training:plan_members", args=[self.plan.pk]),
            ]),
        })

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except ValidationError as exc:
            return HttpResponse("；".join(exc.messages), status=400)

    def post(self, request, *args, **kwargs):
        try:
            if request.POST.get("stage") == "confirm":
                query = confirm_members(actor=request.user, plan=self.plan, token=request.POST.get("token", ""))
                messages.success(request, "已更新计划成员，历史任务分配保持不变。")
                return redirect(self.return_url(query))
            form = PlanMemberActionForm(request.POST)
            if request.POST.get("stage") != "select" or not self.adding or not form.is_valid() or request.POST.get("selection") != "selected":
                raise ValidationError("请选择有效操作和当前页成员。")
            self.object_list = self.get_queryset()
            table = self.get_table()
            ids = normalize_ids(request.POST.getlist("users"))
            if not set(ids) <= {row.record.pk for row in table.page.object_list}:
                raise ValidationError("所选用户不属于当前筛选页，请重新选择。")
            return self.confirmation(preview_members(actor=request.user, plan=self.plan, ids=ids, operation="add",
                                                      return_query=request.GET.urlencode()))
        except ValidationError as exc:
            messages.error(request, "；".join(exc.messages))
            return redirect(self.return_url(request.GET.urlencode()))


class PlanMemberRemoveView(PlanMembersView):
    def get(self, request, *args, **kwargs):
        member = get_object_or_404(TrainingPlanParticipant, pk=kwargs["member_pk"], training_plan=self.plan)
        try:
            return self.confirmation(preview_members(actor=request.user, plan=self.plan, ids=[member.user_id],
                                                      operation="remove", return_query=request.GET.urlencode()))
        except ValidationError as exc:
            messages.error(request, "；".join(exc.messages))
            return redirect(self.return_url(request.GET.urlencode()))

    http_method_names = ["get", "head", "options"]
