from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.services.users import annotate_identity_labels, get_user_display_name
from core.utils.breadcrumbs import Breadcrumb, breadcrumb_link, build_breadcrumbs
from core.utils.forms import StyledFormMixin

from .historical_rosters import confirm_roster, historical_candidates, preview_roster, revoke_roster, roster_history
from .plan_members import require_manager
from .scheduling import visible_plans


class HistoricalCompetitorField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, user):
        label = get_user_display_name(user)
        return label if user.is_active else f"{label}（已停用）"


class HistoricalRosterForm(StyledFormMixin, forms.Form):
    start = forms.DateField(label="开始日期", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    end = forms.DateField(label="结束日期", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    users = HistoricalCompetitorField(
        label="完整应交选手名单", queryset=None, required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox checkbox-primary"}),
    )
    empty = forms.BooleanField(label="确认无人应交", required=False)
    reason = forms.CharField(label="名单依据", max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, plan, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["users"].queryset = annotate_identity_labels(
            historical_candidates(plan),
        ).order_by("last_name", "first_name", "pk")

    def clean(self):
        data = super().clean()
        if "users" in data and bool(data["users"]) == data.get("empty"):
            self.add_error("users", "请选择完整名单，或勾选确认无人应交。")
        return data


class RevokeRosterForm(forms.Form):
    record_id = forms.IntegerField(min_value=1)
    reason = forms.CharField(max_length=2000)


@require_http_methods(["GET", "POST"])
def historical_rosters(request, pk):
    plan = get_object_or_404(visible_plans(request.user), pk=pk)
    actor = require_manager(request.user, plan)
    title = "历史应交选手名单"
    members_url = reverse("training:plan_members", args=[pk])
    url = reverse("training:historical_rosters", args=[pk])
    can_backfill = bool(plan.published_at and plan.schedule_published_at)
    form = None
    context = {
        "title": title, "plan": plan, "members_url": members_url, "can_backfill": can_backfill,
        "breadcrumbs": build_breadcrumbs(request, title, parents=[
            breadcrumb_link(plan.title, "training:plan_detail", args=[pk]),
            Breadcrumb("计划人员管理", members_url),
        ]),
    }
    if request.method == "POST":
        try:
            stage = request.POST.get("stage", "preview")
            if stage == "confirm":
                confirm_roster(actor, plan, request.POST.get("token", ""))
                messages.success(request, "历史应交选手名单已确认。")
                return redirect(url)
            if stage == "revoke":
                revoke_form = RevokeRosterForm(request.POST)
                if not revoke_form.is_valid():
                    raise ValidationError("请填写有效的撤销原因。")
                revoke_roster(actor, plan, **revoke_form.cleaned_data)
                messages.success(request, "历史应交选手名单已撤销。")
                return redirect(url)
            if stage != "preview":
                raise ValidationError("操作无效。")
            form = HistoricalRosterForm(request.POST, plan=plan)
            if form.is_valid():
                data = form.cleaned_data
                snapshot, token = preview_roster(
                    actor, plan, start=data["start"], end=data["end"],
                    ids=[user.pk for user in data["users"]], reason=data["reason"],
                )
                context.update(snapshot=snapshot, token=token, reason=data["reason"])
        except ValidationError as exc:
            context["errors"] = exc.messages
    return render(request, "training/historical_rosters.html", {
        **context, "form": form if form is not None else HistoricalRosterForm(plan=plan),
        "history": roster_history(plan),
    })
