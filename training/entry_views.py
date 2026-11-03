"""排班批量编排及分层撤回的预览、确认页面。"""

from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.http import Http404
from django.http import QueryDict
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.utils.forms import StyledFormMixin
from accounts.services.users import get_user_display_name
from . import entry_operations as operations
from . import scheduling
from .models import TrainingScheduleSlot
from .schedule_forms import plan_coaches
from .schedule_views import get_plan, render


def return_url(plan, query=""):
    allowed = {
        "tab",
        "q",
        "date",
        "date_from",
        "date_to",
        "period",
        "domain",
        "coach",
        "state",
        "mine",
        "sort",
        "page",
    }
    params = QueryDict(query or "")
    clean = QueryDict(mutable=True)
    for key in allowed:
        if key in params:
            clean[key] = params[key]
    return reverse("training:plan_detail", args=[plan.pk]) + ("?" + clean.urlencode() if clean else "")


class EntryOperationForm(StyledFormMixin, forms.Form):
    return_query = forms.CharField(required=False, widget=forms.HiddenInput)
    operation = forms.ChoiceField(
        label="操作",
        choices=[
            ("schedule", "批量排班"),
            ("copy", "复制排班"),
            ("tasks", "批量填写任务"),
            ("swap", "快捷调班"),
            ("clear", "清空排班"),
            ("unused", "设为不安排"),
        ],
    )
    first = forms.ModelChoiceField(label="对调日期一", queryset=None, required=False)
    second = forms.ModelChoiceField(label="对调日期二", queryset=None, required=False)
    slots = forms.ModelMultipleChoiceField(
        label="固定目标时段",
        queryset=TrainingScheduleSlot.objects.none(),
        required=False,
        widget=forms.MultipleHiddenInput,
    )
    days = forms.ModelMultipleChoiceField(label="目标日期（可多选）", queryset=None, required=False)
    date_from = forms.DateField(label="目标开始日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="目标结束日期", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    weekdays = forms.MultipleChoiceField(
        label="目标星期",
        required=False,
        choices=[(str(i), f"星期{label}") for i, label in enumerate("一二三四五六日")],
        widget=forms.CheckboxSelectMultiple,
    )
    periods = forms.MultipleChoiceField(
        label="目标时段", choices=TrainingScheduleSlot.Period.choices, widget=forms.CheckboxSelectMultiple
    )
    source = forms.ModelChoiceField(label="来源日期", queryset=None, required=False)
    copy_mode = forms.ChoiceField(
        label="复制方式",
        choices=[
            ("day", "同一来源日复制到目标日期"),
            ("previous", "目标日期的上周同一天"),
            ("week", "来源日所在周按星期对应复制"),
        ],
        required=False,
    )
    include_duty = forms.BooleanField(label="同时复制值班人员", required=False)
    include_note = forms.BooleanField(label="同时复制日备注", required=False)
    overwrite = forms.BooleanField(label="覆盖已有安排（保留任务，须通过兼容校验）", required=False)
    state = forms.ChoiceField(
        label="排班状态",
        choices=[("scheduled", "已排班"), ("pending", "待排班"), ("rest", "休息"), ("unused", "不安排")],
        required=False,
    )
    domain = forms.ChoiceField(label="领域", required=False)
    coaches = forms.ModelMultipleChoiceField(label="负责教练", queryset=None, required=False)
    titles = forms.CharField(label="任务标题（每行一项）", required=False, widget=forms.Textarea(attrs={"rows": 4}))
    description = forms.CharField(
        label="共同任务说明（Markdown）", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    reason = forms.CharField(
        label="调整原因（已发布或过期修改必填）", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, plan, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan = plan
        self.fields["days"].queryset = self.fields["source"].queryset = plan.schedule_days.order_by("date")
        self.fields["first"].queryset = self.fields["second"].queryset = plan.schedule_days.order_by("date")
        for name in ("days", "source", "first", "second"):
            self.fields[name].label_from_instance = lambda day: day.date.isoformat()
        self.fields["slots"].queryset = TrainingScheduleSlot.objects.filter(day__training_plan=plan)
        self.fields["coaches"].queryset = plan_coaches(plan)
        self.fields["coaches"].label_from_instance = get_user_display_name
        links = plan.training_cycle.skill_tree_version_links.select_related("technical_domain")
        self.fields["domain"].choices = [
            ("", "请选择领域"),
            *[(str(link.technical_domain_id), str(link.technical_domain)) for link in links],
            ("other", "其他"),
        ]
        if not scheduling.can_schedule(user, plan):
            self.fields["operation"].choices = [("tasks", "批量填写任务")]
        elif not user.has_perm("training.add_trainingtask"):
            self.fields["operation"].choices = [
                (value, label) for value, label in self.fields["operation"].choices if value != "tasks"
            ]
        operation = self.data.get("operation") if self.is_bound else self.initial.get("operation")
        if operation == "swap":
            configured = set(
                TrainingScheduleSlot.objects.filter(day__training_plan=plan, is_configured=True).values_list(
                    "period", flat=True
                )
            )
            self.fields["periods"].choices = [
                (value, label) for value, label in TrainingScheduleSlot.Period.choices if value in configured
            ]
            if not self.is_bound:
                self.initial["periods"] = [value for value, _ in self.fields["periods"].choices]

    def clean(self):
        data = super().clean()
        if data.get("operation") == "copy" and data.get("copy_mode") != "previous" and not data.get("source"):
            self.add_error("source", "请选择来源日期。")
        if data.get("operation") == "tasks":
            titles = [line.strip() for line in data.get("titles", "").splitlines() if line.strip()]
            if not titles or any(len(title) > 180 for title in titles):
                self.add_error("titles", "请填写任务标题，每项不超过180字。")
            data["titles"] = titles
        if data.get("operation") == "schedule":
            domain = data.get("domain")
            state = data.get("state") or "scheduled"
            if state == "scheduled" and not domain:
                self.add_error("domain", "请选择领域。")
            coaches = list(data.get("coaches", []))
            values = {
                "kind": ("general" if domain == "other" else "technical") if state == "scheduled" else state,
                "domains": [int(domain)] if domain and domain.isdecimal() else [],
                "primary_domain": None,
                "coaches_all": False,
                "coaches": [person.pk for person in coaches],
            }
            scheduling.validate_slot(
                self.plan, {"period": "morning", **values}, publishing=True if state == "scheduled" else False
            )
            data["schedule"] = values
        return data

    def command(self):
        data = operations.serial_values(self.cleaned_data)
        for key in ("date_from", "date_to"):
            data[key] = data[key].isoformat() if data[key] else None
        return data


@require_http_methods(["GET", "POST"])
def entry_operation(request, pk):
    raise PermissionDenied("本版本暂不开放批量编排和快捷调班。")
    plan = get_plan(request.user, pk)
    assigned = TrainingScheduleSlot.objects.filter(
        day__training_plan=plan, coaches=request.user, is_configured=True, kind__in=scheduling.ACTIVE_KINDS
    )
    if not scheduling.can_schedule(request.user, plan) and not (
        request.user.has_perm("training.add_trainingtask") and assigned.exists()
    ):
        raise PermissionDenied
    if request.method == "POST" and request.POST.get("token"):
        try:
            result = operations.confirm(plan, request.user, request.POST["token"])
        except (ValidationError, signing.BadSignature) as exc:
            return render(
                request,
                "training/entry_operation.html",
                {"plan": plan, "error": str(exc), "return_url": return_url(plan)},
            )
        data = signing.loads(request.POST["token"], salt="training.entries", max_age=600)
        messages.success(request, "变更已提交审批，批准前原安排保持不变。" if result else "批量操作已完成。")
        return redirect(return_url(plan, data.get("return_query", "")))
    initial = {
        "operation": request.GET.get("operation", "schedule"),
        "periods": request.GET.getlist("period") or TrainingScheduleSlot.Period.values,
        "source": request.GET.get("source"),
        "slots": request.GET.getlist("slots"),
        "days": request.GET.getlist("days"),
        "return_query": request.GET.get("return_query", ""),
    }
    form = EntryOperationForm(
        request.POST if request.method == "POST" else None, initial=initial, plan=plan, user=request.user
    )
    preview = None
    if request.method == "POST" and form.is_valid():
        try:
            preview = operations.preview(plan, request.user, form.command())
        except ValidationError as exc:
            form.add_error(None, exc)
    readable_rows = []
    if preview:
        from types import SimpleNamespace
        from .schedule_history import decorate_history

        records = [SimpleNamespace(before=row["before"], after=row["after"]) for row in preview["rows"]]
        decorate_history(records)
        readable_rows = [
            {"label": row["label"], "diff": record.display_diff}
            for row, record in zip(preview["rows"], records, strict=True)
        ]
    return render(
        request,
        "training/entry_operation.html",
        {
            "plan": plan,
            "form": form,
            "preview": preview,
            "readable_rows": readable_rows,
            "selected_targets": form.fields["slots"]
            .queryset.filter(pk__in=[int(value) for value in form["slots"].value() or [] if str(value).isdecimal()])
            .select_related("day"),
            "return_url": return_url(plan, request.POST.get("return_query", request.GET.get("return_query", ""))),
            "token": signing.dumps(preview, salt="training.entries", compress=True) if preview else "",
        },
    )


class WithdrawForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(label="撤回原因", widget=forms.Textarea(attrs={"rows": 3}))
    return_query = forms.CharField(required=False, widget=forms.HiddenInput)


@require_http_methods(["GET", "POST"])
def publish_all_tasks(request, pk):
    from . import plan_publish

    plan = get_plan(request.user, pk)
    error, result, token = "", None, ""
    try:
        if request.method == "POST":
            data = signing.loads(request.POST.get("token", ""), salt="training.publish_all", max_age=600)
            if data["user"] != request.user.pk or data["plan"] != plan.pk:
                raise PermissionDenied
            plan_publish.publish(plan, request.user, data["digest"])
            messages.success(request, "全部任务草稿已发布。")
            return redirect("training:plan_detail", pk=plan.pk)
        result = plan_publish.preview(plan, request.user)
        if result["can_confirm"]:
            token = signing.dumps({"user": request.user.pk, "plan": plan.pk, "digest": result["digest"]},
                                  salt="training.publish_all", compress=True)
    except (ValidationError, signing.BadSignature) as exc:
        error = "；".join(exc.messages) if isinstance(exc, ValidationError) else "预览已过期或被修改，请重新预览。"
    return render(request, "training/plan_publish.html", {"plan": plan, "result": result, "token": token, "error": error})


@require_http_methods(["GET", "POST"])
def clear_plan(request, pk, action):
    from . import plan_clear

    plan = get_plan(request.user, pk)
    labels = {"withdraw_tasks": "撤回全部任务发布", "clear_tasks": "清空全部任务", "clear_schedule": "清空全部排班"}
    if action not in labels:
        raise Http404
    form = WithdrawForm(request.POST if request.method == "POST" else None)
    preview, token, error = None, "", ""
    try:
        preview = plan_clear.state(plan, request.user, action)
        if request.method == "POST" and request.POST.get("token"):
            data = signing.loads(request.POST["token"], salt="training.plan_clear", max_age=600)
            if data["user"] != request.user.pk or data["plan"] != plan.pk or data["action"] != action:
                raise PermissionDenied
            plan_clear.execute(plan, request.user, action, data["reason"], data["digest"])
            messages.success(request, f"{labels[action]}已完成。")
            return redirect("training:plan_detail", pk=plan.pk)
        if request.method == "POST" and form.is_valid():
            token = signing.dumps({"user": request.user.pk, "plan": plan.pk, "action": action,
                                   "reason": form.cleaned_data["reason"], "digest": preview["digest"]},
                                  salt="training.plan_clear", compress=True)
    except (ValidationError, signing.BadSignature) as exc:
        error = "；".join(exc.messages) if isinstance(exc, ValidationError) else "预览已过期或被修改，请重新预览。"
    return render(request, "training/plan_clear.html", {"plan": plan, "action_label": labels[action],
                  "action": action, "preview": preview, "form": form, "token": token, "error": error})


@require_http_methods(["GET", "POST"])
def withdraw_publication(request, pk, level, task_id=None):
    plan = get_plan(request.user, pk)
    try:
        task, guard = operations.withdrawal_state(plan, request.user, level, task_id)
    except plan.tasks.model.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        return render(request, "training/entry_withdraw.html", {"plan": plan, "error": str(exc)}, status=400)
    form = WithdrawForm(
        request.POST if request.method == "POST" else None,
        initial={"return_query": request.GET.get("return_query", "")},
    )
    token, error = "", ""
    if request.method == "POST" and request.POST.get("token"):
        try:
            operations.withdraw(plan, request.user, request.POST["token"])
        except (ValidationError, signing.BadSignature) as exc:
            error = str(exc)
        else:
            data = signing.loads(request.POST["token"], salt="training.withdraw", max_age=600)
            messages.success(request, "已撤回本层发布，下级发布状态和历史分配均已保留。")
            return redirect(return_url(plan, data.get("return_query", "")))
    elif request.method == "POST" and form.is_valid():
        token = signing.dumps(
            {
                "user": request.user.pk,
                "plan": plan.pk,
                "level": level,
                "task": task_id,
                "guard": guard,
                "reason": form.cleaned_data["reason"],
                "return_query": form.cleaned_data["return_query"],
            },
            salt="training.withdraw",
            compress=True,
        )
    return render(
        request,
        "training/entry_withdraw.html",
        {
            "plan": plan,
            "task": task,
            "level": {"plan": "计划", "schedule": "排班", "task": "任务"}[level],
            "form": form,
            "token": token,
            "error": error,
            "return_url": return_url(plan, request.POST.get("return_query", request.GET.get("return_query", ""))),
        },
    )
