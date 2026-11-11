from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from accounts.services.users import annotate_identity_labels, get_user_display_name
from core.utils.breadcrumbs import breadcrumb_link, build_breadcrumbs
from core.utils.forms import StyledFormMixin
from meetings.widgets import RecipientSelect

from .log_exemptions import (
    ROLES, confirm_exemption, exemption_candidates, exemption_history, exemption_rules, preview_exemption,
    require_admin,
)
from .plan_people import plan_people_search_response
from .scheduling import visible_plans


class ExemptionUserSelect(RecipientSelect):
    template_name = "training/widgets/plan_people.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"].update(
            search_url=reverse("training:plan_log_exemption_search", args=[self.plan_id]),
            picker_title="免交人员",
        )
        return context


class ExemptionForm(StyledFormMixin, forms.Form):
    operation = forms.ChoiceField(label="操作", choices=[
        ("add", "新增规则"), ("replace", "替换规则"), ("end", "结束规则"),
    ])
    target = forms.TypedChoiceField(label="要替换或结束的规则", coerce=int, empty_value=None, required=False)
    role = forms.MultipleChoiceField(
        label="免交角色", choices=[(key, f"全部{label}") for key, label in ROLES.items()], required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox checkbox-primary"}),
        help_text="勾选后，该组在确认时名单中的所有成员都会免交训练日志。可以同时勾选两组。",
    )
    user = forms.ModelMultipleChoiceField(
        label="指定人员", queryset=None, required=False, widget=ExemptionUserSelect,
        help_text="可单独选择一人或多人，也可补选整组免交范围之外的人员。",
    )
    start = forms.DateField(label="生效日期", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    end = forms.DateField(
        label="结束日期", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        required=False, help_text="新增或替换时留空表示持续到计划结束，含结束当天。",
    )
    reason = forms.CharField(label="原因", max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, plan, rules, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].choices = [("", "请选择")] + [
            (pk, f"#{pk} · {rule['label']} · {rule['start']} 至 {rule['end']} · {'、'.join(rule['names'])}")
            for pk, rule in rules.items()
        ]
        users = annotate_identity_labels(exemption_candidates(plan)).order_by("last_name", "first_name", "pk")
        field = self["user"]
        field.field.queryset = users
        field.field.widget.plan_id = plan.pk
        selected_ids = [pk for pk in (field.value() or []) if str(pk).isascii() and str(pk).isdecimal()]
        field.field.widget.selected = [
            {"id": user.pk, "label": get_user_display_name(user)}
            for user in users.filter(pk__in=selected_ids)
        ]

    def parameters(self):
        data = self.cleaned_data
        return {
            "operation": data["operation"], "target": data["target"],
            "roles": [role for role in ROLES if role in data["role"]],
            "user_ids": sorted(user.pk for user in data["user"]),
            "start": data["start"].isoformat(), "end": data["end"].isoformat() if data["end"] else None,
            "reason": data["reason"],
        }


@require_GET
def plan_log_exemption_search(request, pk):
    require_admin(request.user)
    plan = get_object_or_404(visible_plans(request.user), pk=pk)
    return plan_people_search_response(request, exemption_candidates(plan))


@require_http_methods(["GET", "POST"])
def plan_log_exemptions(request, pk):
    require_admin(request.user)
    plan = get_object_or_404(visible_plans(request.user), pk=pk)
    title = "训练日志免交"
    context = {
        "title": title, "plan": plan,
        "breadcrumbs": build_breadcrumbs(request, title, parents=[
            breadcrumb_link(plan.title, "training:plan_detail", args=[pk]),
        ]),
    }
    is_preview = request.method == "POST" and "token" not in request.POST
    history = list(exemption_history(plan))
    rules = exemption_rules(history)
    form = ExemptionForm(
        request.POST if is_preview else None, plan=plan, rules=rules,
        initial={"start": min(max(timezone.localdate(), plan.start_date), plan.end_date)},
    )
    if request.method == "POST":
        try:
            if not is_preview:
                confirm_exemption(request.user, plan, request.POST["token"])
                messages.success(request, "训练日志免交规则已保存。")
                return redirect("training:plan_log_exemptions", pk=pk)
            if form.is_valid():
                params = form.parameters()
                snapshot, token = preview_exemption(request.user, plan, params)
                context.update(snapshot=snapshot, token=token, reason=params["reason"])
        except ValidationError as exc:
            context["errors"] = exc.messages
    return render(request, "training/plan_log_exemptions.html", {
        **context, "form": form, "rules": rules, "history": reversed(history),
    })
