"""计划参与选手列表、添加和退出确认页面。"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import BooleanField, Case, CharField, F, Value, When
from django.http import HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_tables2 import SingleTableView

from accounts.services.user_management import filter_users, normalize_ids
from accounts.user_management_forms import UserFilterForm
from core.utils.breadcrumbs import breadcrumb_link
from core.utils.listing import FilterableListMixin, ListFilterSpec
from core.utils.mixins import TitleMixin

from .member_tables import PlanCandidateTable, PlanMemberTable
from .models import TrainingPlanParticipant
from .plan_members import (
    ParticipantGroupsForm, PlanMemberActionForm, PlanRosterForm, candidates, change_coaches, change_duty, confirm_members,
    ordered_duty, preview_members, require_manager, save_roster,
)
from .plan_people import eligible_staff
from .scheduling import visible_plans


def staff_context(plan, role, *, error=""):
    from collections import Counter
    from accounts.services.users import user_name_search_terms

    eligible = list(eligible_staff(role, plan).select_related("profile").prefetch_related("groups")
                    .order_by("last_name", "first_name", "pk"))
    current = list((ordered_duty(plan) if role == "duty_personnel" else plan.responsible_coaches.all())
                   .select_related("profile").prefetch_related("groups"))
    all_people = {user.pk: user for user in [*eligible, *current]}
    names = Counter((user.last_name + user.first_name).strip() for user in all_people.values())
    notes = Counter(((user.last_name + user.first_name).strip(), getattr(getattr(user, "profile", None),
                    "name_disambiguation", "").strip()) for user in all_people.values())
    current_ids = {user.pk for user in current}
    eligible_ids = {user.pk for user in eligible}
    max_order = max((user.duty_order for user in current), default=0) if role == "duty_personnel" else 0

    def row(user, index=0):
        name = (user.last_name + user.first_name).strip() or "未填写姓名"
        profile = getattr(user, "profile", None)
        note = (getattr(profile, "name_disambiguation", "") or "").strip()
        duplicate = names[name] > 1
        invalid = duplicate and (not note or notes[(name, note)] > 1)
        terms = user_name_search_terms(name, getattr(profile, "name_pronunciation", "") or "")
        return {"user": user, "label": f"{name}（{note}）" if duplicate and note else name,
                "invalid": invalid, "search": " ".join(terms).lower(),
                "roles": " ".join(str(group.pk) for group in user.groups.all()) if user.pk in eligible_ids else "",
                "ineligible": user.pk not in eligible_ids,
                "order": getattr(user, "duty_order", max_order + index)}

    return {"plan": plan, "role": role, "is_duty": role == "duty_personnel", "error": error,
            "current": [row(user) for user in current],
            "role_options": sorted({(group.pk, group.name) for user in eligible for group in user.groups.all()},
                                   key=lambda item: (item[1], item[0])),
            "candidates": [row(user, i) for i, user in enumerate(
                (user for user in eligible if user.pk not in current_ids), 1)]}


def staff_action(request, pk, role):
    from django.views.decorators.http import require_POST

    @require_POST
    def perform(request):
        if role not in {"responsible_coaches", "duty_personnel"}:
            return HttpResponse(status=404)
        plan = get_object_or_404(visible_plans(request.user), pk=pk)
        require_manager(request.user, plan)
        error = ""
        try:
            operation = request.POST.get("operation")
            if operation == "remove":
                ids = normalize_ids([request.POST.get("user")])
            else:
                ids = normalize_ids(request.POST.getlist("users"))
            if operation == "add":
                context = staff_context(plan, role)
                permitted = {item["user"].pk for item in context["candidates"] if not item["invalid"]}
                if not set(ids) <= permitted:
                    raise ValidationError("所选人员不符合条件或同名备注无法区分，请刷新后重试。")
            if role == "responsible_coaches":
                if operation not in {"add", "remove"}:
                    raise ValidationError("操作无效。")
                change_coaches(actor=request.user, plan=plan, ids=ids, operation=operation)
            else:
                orders = {pk: request.POST.get(f"order_{pk}", "0") for pk in ids}
                change_duty(actor=request.user, plan=plan, operation=operation, orders=orders)
        except ValidationError as exc:
            error = "；".join(exc.messages)
        if request.htmx:
            return render(request, "training/partials/plan_staff_section.html", staff_context(plan, role, error=error))
        (messages.error if error else messages.success)(request, error or "人员名单已更新。")
        return redirect(reverse("training:plan_members", args=[pk]) + ("#duty" if role == "duty_personnel" else "#coaches"))
    return perform(request)


class PlanMembersView(FilterableListMixin, TitleMixin, SingleTableView):
    template_name = "training/plan_members.html"
    title = "计划人员管理"
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
            ListFilterSpec("q", "搜索用户", "search", placeholder="姓名、拼音或学号"),
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
        from collections import Counter

        people = list(self.model.objects.filter(
            training_cycle_memberships__training_cycle_id=self.plan.training_cycle_id,
            training_cycle_memberships__role="competitor",
        ).values_list("pk", "last_name", "first_name", "profile__name_disambiguation"))
        names = Counter((last + first).strip() for _, last, first, _ in people)
        notes = Counter(((last + first).strip(), (note or "").strip()) for _, last, first, note in people)
        labels, invalid = [], []
        for pk, last, first, note in people:
            name, note = (last + first).strip(), (note or "").strip()
            if names[name] > 1:
                if not note or notes[(name, note)] > 1:
                    invalid.append(pk)
                if note:
                    labels.append(When(pk=pk, then=Value(f"{name or '未填写姓名'}（{note}）")))
        queryset = queryset.annotate(
            identity_label=Case(*labels, default=Value(""), output_field=CharField()),
            identity_invalid=Case(When(pk__in=invalid, then=Value(True)), default=Value(False),
                                  output_field=BooleanField()),
        )
        return filter_users(queryset, filters.cleaned_data, annotate_identity=False).order_by(
            F("profile__join_date").desc(nulls_last=True), "-pk")

    def get_table_class(self):
        return PlanCandidateTable if self.adding else PlanMemberTable

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            plan=self.plan, adding=self.adding,
            coach_section=staff_context(self.plan, "responsible_coaches"),
            duty_section=staff_context(self.plan, "duty_personnel"),
            list_filter_hidden_fields=[{"name": "mode", "value": self.request.GET["mode"]}]
            if self.adding else [],
            list_filter_reset_url=f"{self.request.path}?mode={self.request.GET['mode']}" if self.adding else self.request.path,
            participant_action_url=self.return_url(self.request.GET.urlencode()),
            groups_form=ParticipantGroupsForm() if self.adding else None,
        )
        return context

    def return_url(self, query):
        params = QueryDict(query).copy()
        for key in list(params):
            if key not in {"mode", "q", "role", "participation", "sort", "page"}:
                del params[key]
        return reverse("training:plan_members", args=[self.plan.pk]) + ("?" + params.urlencode() if params else "")

    def get(self, request, *args, **kwargs):
        try:
            if request.htmx and request.GET.get("section") == "participants":
                return self.participant_section()
            return super().get(request, *args, **kwargs)
        except ValidationError as exc:
            return HttpResponse("；".join(exc.messages), status=400)

    def participant_section(self, *, error="", success="", reset=False):
        if reset:
            self.request.GET = QueryDict("")
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        url = reverse("training:plan_members", args=[self.plan.pk])
        context.update(participant_error=error, participant_success=success, list_filter_url=url)
        context["list_filter_reset_url"] = url + ("?mode=add" if self.adding else "")
        response = render(self.request, "training/partials/plan_participant_section.html", context)
        if reset:
            response["HX-Push-Url"] = url
        return response

    def post(self, request, *args, **kwargs):
        try:
            if request.POST.get("stage") == "roster":
                role = request.POST.get("roster")
                if role != "duty_personnel":
                    raise ValidationError("人员职责无效。")
                form = PlanRosterForm(request.POST, plan=self.plan, role=role)
                if not form.is_valid():
                    raise ValidationError(form.errors.as_data())
                save_roster(request.user, self.plan, role, {user.pk for user in form.cleaned_data[role]})
                messages.success(request, "已更新值班人员。")
                return redirect(self.return_url(request.GET.urlencode()))
            if request.POST.get("stage") == "remove_coach":
                change_coaches(actor=request.user, plan=self.plan, ids=[request.POST.get("user")], operation="remove")
                messages.success(request, "已移除负责教练。")
                return redirect(self.return_url(request.GET.urlencode()) + "#coaches")
            if request.POST.get("stage") == "confirm_groups" and self.adding:
                confirm_members(actor=request.user, plan=self.plan, token=request.POST.get("token", ""))
                messages.success(request, "已添加预览名单中的选手。")
                return redirect(reverse("training:plan_members", args=[self.plan.pk]) + "#participants")
            form = PlanMemberActionForm(request.POST)
            if request.POST.get("stage") != "select" or not self.adding or not form.is_valid() or request.POST.get("selection") != "selected":
                raise ValidationError("请选择有效操作和当前页成员。")
            self.object_list = self.get_queryset()
            table = self.get_table()
            selected = request.POST.getlist("users")
            ids = normalize_ids(selected) if selected else []
            if not set(ids) <= {row.record.pk for row in table.page.object_list}:
                raise ValidationError("所选用户不属于当前筛选页，请重新选择。")
            if request.POST.get("group_selection") == "1":
                groups_form = ParticipantGroupsForm(request.POST)
                if not groups_form.is_valid():
                    raise ValidationError("请选择有效的用户角色。")
                groups = list(groups_form.cleaned_data["groups"])
                audience = ""
                if not groups_form.cleaned_data["elite_class"] and len(groups) == 1 and self.plan.implementation_audience == "精英班":
                    audience = groups[0].name
                preview = preview_members(
                    actor=request.user, plan=self.plan, ids=set(ids) | groups_form.selected_ids(self.plan),
                    operation="add", audience=audience,
                )
                return render(request, "training/plan_participant_preview.html", {
                    "preview": preview, "plan": self.plan, "return_url": self.return_url(request.GET.urlencode()),
                })
            preview = preview_members(actor=request.user, plan=self.plan, ids=ids, operation="add")
            confirm_members(actor=request.user, plan=self.plan, token=preview["token"])
            if request.htmx:
                return self.participant_section(success="已添加计划成员，历史任务分配保持不变。", reset=True)
            messages.success(request, "已添加计划成员，历史任务分配保持不变。")
            return redirect(reverse("training:plan_members", args=[self.plan.pk]) + "#participants")
        except ValidationError as exc:
            if request.htmx and request.POST.get("stage") == "select":
                return self.participant_section(error="；".join(exc.messages))
            messages.error(request, "；".join(exc.messages))
            return redirect(self.return_url(request.GET.urlencode()))


class PlanMemberRemoveView(PlanMembersView):
    def post(self, request, *args, **kwargs):
        member = get_object_or_404(TrainingPlanParticipant, pk=kwargs["member_pk"], training_plan=self.plan)
        try:
            preview = preview_members(actor=request.user, plan=self.plan, ids=[member.user_id], operation="remove")
            confirm_members(actor=request.user, plan=self.plan, token=preview["token"])
            if request.htmx:
                return self.participant_section(success="成员已退出，历史记录和执行保持不变。")
            messages.success(request, "成员已退出，历史记录和执行保持不变。")
        except ValidationError as exc:
            if request.htmx:
                return self.participant_section(error="；".join(exc.messages))
            messages.error(request, "；".join(exc.messages))
        return redirect(self.return_url(request.GET.urlencode()) + "#participants")

    http_method_names = ["post", "options"]
