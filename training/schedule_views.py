from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import Case, IntegerField, Prefetch, Q, When
from django.forms import formset_factory
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render as django_render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.services.users import get_user_display_name
from . import scheduling as service
from .models import TrainingScheduleSlot, TrainingScheduleChange
from .schedule_forms import DayScheduleForm, SlotScheduleForm, SlotTaskForm, SkillCorrectionForm
from .entry_navigation import filters_for, editor_suffix, next_entry
from .selectors import visible_training_tasks_for
from .views import TrainingPlanDetailView


def row_updates(request, response, plan, slot_ids, day_ids=None):
    # 无筛选时只替换本页受影响行；筛选可能改变成员时重取结果。
    import copy
    import json
    from urllib.parse import urlsplit
    from django.http import QueryDict
    from django.template.loader import render_to_string
    from django.urls import reverse
    current = urlsplit(request.headers.get("HX-Current-URL", ""))
    if not request.htmx or current.path != reverse("training:plan_detail", args=[plan.pk]):
        return response
    params = QueryDict(current.query)
    if any(value for key, value in params.items() if key not in {"tab", "page", "sort", "fragment"}):
        return response
    from .schedule_display import plan_context
    local_request = copy.copy(request)
    local_request.GET = params
    view = PlanDetailView()
    view.setup(local_request)
    view.object = plan
    context = plan_context(view, {"plan": plan})
    days = set(day_ids or TrainingScheduleSlot.objects.filter(pk__in=slot_ids).values_list("day_id", flat=True))
    rows = [row for row in context["table"].rows if (row.record.day_id in days if context["task_tab"] else row.record.pk in days)]
    response.content += render_to_string("training/entry_row_updates.html", {"rows": rows}, request=local_request).encode()
    response["HX-Trigger"] = json.dumps({"scheduleChanged": {"rowsUpdated": True}})
    return response


def render(request, template, context=None, **kwargs):
    from core.utils.breadcrumbs import build_breadcrumbs, breadcrumb_link

    context = dict(context or {})
    plan = context.get("plan")
    title = {
        "training/schedule_edit.html": "编辑排班",
        "training/slot_task_form.html": "填写训练任务",
        "training/task_skills.html": "维护任务关联",
        "training/task_select_slot.html": "选择计划和时段",
        "training/process_detail.html": "训练执行",
        "training/personal_form.html": "自主训练任务",
        "training/schedule_clear.html": "清空排班确认",
        "training/slot_tasks_clear.html": "清空任务确认",
        "training/workbook_import.html": "导入训练计划",
    }.get(template, "训练计划")
    parents = [breadcrumb_link("训练计划", "training:plan_list")] if request.user.has_perm("training.view_trainingplan") else []
    if plan and parents and context.get("can_view_plan", True):
        parents.append(breadcrumb_link(plan.title, "training:plan_detail", args=[plan.pk]))
    context.update(
        title=title, title_icon="icon-[tabler--calendar]", breadcrumbs=build_breadcrumbs(request, title, parents)
    )
    return django_render(request, template, context, **kwargs)


def get_plan(user, pk):
    return get_object_or_404(service.visible_plans(user), pk=pk)


@require_http_methods(["GET", "POST"])
def swap_schedule(request, pk):
    from .entry_views import entry_operation
    if request.method == "POST":
        data = request.POST.copy()
        data["operation"] = "swap"
        request.POST = data
    else:
        data = request.GET.copy()
        data["operation"] = "swap"
        request.GET = data
    return entry_operation(request, pk)


def plan_slots(plan, user):
    return (
        TrainingScheduleSlot.objects.filter(day__training_plan=plan, is_configured=True)
        .select_related(
            "day__training_plan",
            "primary_domain",
        )
        .prefetch_related(
            "domains",
            "coaches",
            "day__duty_coaches",
            Prefetch(
                "tasks",
                queryset=visible_training_tasks_for(user).order_by("order", "pk"),
                to_attr="visible_tasks",
            ),
        )
        .annotate(
            period_order=Case(
                *[When(period=value, then=index) for index, value in enumerate(TrainingScheduleSlot.Period.values)],
                output_field=IntegerField(),
            )
        )
        .order_by("day__date", "period_order")
    )


class PlanDetailView(TrainingPlanDetailView):
    def get_queryset(self):
        return (
            service.visible_plans(self.request.user)
            .select_related("training_cycle")
            .prefetch_related("schedulers", "approvers", "task_managers")
        )

    def get_template_names(self):
        if self.request.htmx and self.request.GET.get("fragment") == "results":
            return ["training/schedule_results.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        from .schedule_display import plan_context
        return plan_context(self, super().get_context_data(**kwargs))


def _success(request, plan, text):
    if request.htmx:
        return HttpResponse(f'<p class="alert alert-success">{text}</p>', headers={"HX-Trigger": "scheduleChanged"})
    messages.success(request, text)
    return redirect("training:plan_detail", pk=plan.pk)


def _error(request, plan, exc):
    if request.htmx:
        return render(request, "training/schedule_error.html", {"errors": exc.messages, "plan": plan})
    messages.error(request, "；".join(exc.messages))
    return redirect("training:plan_detail", pk=plan.pk)


@require_POST
def initialize(request, pk):
    plan = get_plan(request.user, pk)
    if not service.can_schedule(request.user, plan):
        raise PermissionDenied
    return _error(request, plan, ValidationError("日期框架在创建计划时自动生成；旧计划请管理员按升级说明预览并显式补录。"))


@require_POST
def publish(request, pk):
    plan = get_plan(request.user, pk)
    try:
        service.publish_schedule(plan, request.user)
    except ValidationError as exc:
        return _error(request, plan, exc)
    return _success(request, plan, "排班已发布，已发布任务将在计划发布后对选手可见。")


@require_http_methods(["GET", "POST"])
def schedule_bulk(request, pk):
    raise PermissionDenied("本版本暂不开放批量排班。")
    from django.core import signing
    from django.db import transaction
    plan = get_plan(request.user, pk)
    if not service.can_schedule(request.user, plan):
        raise PermissionDenied
    if request.method == "GET" and request.GET.get("operation") == "edit":
        return edit_schedule(request, pk)
    try:
        if plan.schedule_published_at:
            raise ValidationError("定稿后不能清空排班。")
        if request.method == "POST":
            data = signing.loads(request.POST.get("token", ""), salt="training.clear", max_age=600)
            if data["user"] != request.user.pk or data["plan"] != plan.pk:
                raise PermissionDenied
            with transaction.atomic():
                result = service.save_schedule(plan, request.user, data["payload"], request.POST.get("reason", ""))
            return _success(request, plan, "清空申请已提交审批，原安排保持不变。" if isinstance(result, TrainingScheduleChange) else "所选日期排班已清空，变更历史已保留。")
        ids = request.GET.getlist("days")
        if request.GET.get("operation") != "clear" or not ids or any(not value.isdecimal() for value in ids):
            raise ValidationError("请选择日期和有效操作。")
        days = list(plan.schedule_days.filter(pk__in=ids))
        if len(days) != len(set(ids)):
            raise PermissionDenied
        payload = []
        for day in days:
            before = service.day_snapshot(day)
            payload.append({"type": "day", "id": day.pk, "revision": day.revision, "before": before, "after": before | {"duty_all": False, "duty_coaches": [], "note": ""}})
            for slot in day.slots.all():
                if not slot.is_configured:
                    continue
                if slot.tasks.exists():
                    raise ValidationError("所选日期含既有任务，不能清空。")
                before = service.slot_snapshot(slot)
                payload.append({"type": "slot", "id": slot.pk, "revision": slot.revision, "before": before, "after": before | {"kind": "pending", "domains": [], "primary_domain": None, "coaches_all": False, "coaches": []}})
        token = signing.dumps({"user": request.user.pk, "plan": plan.pk, "payload": payload}, salt="training.clear")
    except (signing.BadSignature, KeyError, ValidationError) as exc:
        return _error(request, plan, ValidationError(str(exc)))
    return render(request, "training/schedule_clear.html", {"plan": plan, "days": days, "token": token, "is_fragment": bool(request.htmx)})


def _serial(form):
    result = {}
    for name, value in form.cleaned_data.items():
        if name in {"state", "domain_choice"}:
            continue
        if name in {"object_id", "revision"}:
            continue
        if hasattr(value, "values_list"):
            value = sorted(value.values_list("pk", flat=True))
        elif hasattr(value, "pk"):
            value = value.pk
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        result[name] = value
    return result


@require_http_methods(["GET", "POST"])
def edit_schedule(request, pk):
    plan = get_plan(request.user, pk)
    if not service.can_schedule(request.user, plan):
        raise PermissionDenied
    source = request.POST if request.method == "POST" else request.GET
    day_ids = source.getlist("days")
    if not day_ids or any(not value.isdigit() for value in day_ids):
        return _error(request, plan, ValidationError("请选择要调整的日期。"))
    days = list(plan.schedule_days.filter(pk__in=set(day_ids)).order_by("date"))
    if len(days) != len(set(day_ids)):
        raise PermissionDenied
    slots = list(TrainingScheduleSlot.objects.filter(day__in=days, is_configured=True).select_related("day").order_by("day__date", "pk"))
    slot_id = source.get("slot", "")
    day_only = source.get("day_only") == "1"
    if not plan.published_at:
        return _error(request, plan, ValidationError("请先发布计划，再填写排班。"))
    if len(days) != 1 or not (slot_id or day_only):
        raise PermissionDenied("本版本仅支持单时段或单日信息编辑。")
    editable_days = days
    if slot_id:
        if not slot_id.isdecimal() or len(days) != 1 or day_only:
            raise PermissionDenied
        slots = [slot for slot in slots if slot.pk == int(slot_id)]
        if len(slots) != 1:
            raise PermissionDenied
        editable_days = []
    # 日入口编辑当天全部已启用时段；时段入口只编辑该时段。
    slots.sort(key=lambda slot: TrainingScheduleSlot.Period.values.index(slot.period))
    DayForms = formset_factory(
        DayScheduleForm, extra=0, max_num=len(editable_days), validate_max=True, min_num=len(editable_days), validate_min=True
    )
    SlotForms = formset_factory(
        SlotScheduleForm, extra=0, max_num=len(slots), validate_max=True, min_num=len(slots), validate_min=True
    )
    data = request.POST if request.method == "POST" else None
    day_forms = DayForms(
        data,
        prefix="day",
        form_kwargs={"plan": plan},
        initial=[service.day_snapshot(day) | {"object_id": day.pk, "revision": day.revision, "duty_coaches": [] if day.duty_all else list(day.duty_coaches.values_list("pk", flat=True))} for day in editable_days],
    )
    slot_forms = SlotForms(
        data,
        prefix="slot",
        form_kwargs={"plan": plan},
        initial=[
            service.slot_snapshot(slot)
            | {"object_id": slot.pk, "revision": slot.revision, "date_label": slot.day.date.isoformat(), "period_label": slot.get_period_display(), "coaches": [] if slot.coaches_all else list(slot.coaches.values_list("pk", flat=True))}
            for slot in slots
        ],
    )
    unified_form = SlotScheduleForm(plan=plan, prefix="unified") if day_only else None
    if unified_form:
        for field in unified_form.fields.values():
            field.required = False
    error = ""
    if request.method == "POST" and request.POST.get("action", "save") != "save":
        raise PermissionDenied("请从计划详情统一发布排班。")
    if request.method == "POST" and day_forms.is_valid() and slot_forms.is_valid():
        payload = []
        try:
            for formset, objects, kind, snapshot in (
                (day_forms, editable_days, "day", service.day_snapshot),
                (slot_forms, slots, "slot", service.slot_snapshot),
            ):
                mapping = {obj.pk: obj for obj in objects}
                ids = [form.cleaned_data["object_id"] for form in formset]
                if len(set(ids)) != len(mapping) or set(ids) != set(mapping):
                    raise PermissionDenied
                for form in formset:
                    obj = mapping[form.cleaned_data["object_id"]]
                    after = _serial(form)
                    before = snapshot(obj)
                    after["has_been_filled"] = before["has_been_filled"]
                    if kind == "slot" and after.get("coaches_all") and before["coaches_all"]:
                        after["coaches"] = before["coaches"]
                    if kind == "day" and after.get("duty_all") and before["duty_all"] and not after["duty_coaches"]:
                        after["duty_coaches"] = before["duty_coaches"]
                    if obj.revision != form.cleaned_data["revision"]:
                        raise ValidationError("安排已经变化，请刷新后重新提交。")
                    if before != after:
                        payload.append(
                            {"type": kind, "id": obj.pk, "revision": obj.revision, "before": before, "after": after}
                        )
            from django.db import transaction
            result = None
            with transaction.atomic():
                if payload:
                    result = service.save_schedule(plan, request.user, payload, request.POST.get("reason", ""))
                else:
                    raise ValidationError("没有需要保存的调整。")
        except ValidationError as exc:
            error = "；".join(exc.messages)
        except IntegrityError:
            error = "日期或时段发生冲突，请检查后重新提交。"
        else:
            if request.htmx:
                following = next_entry(request, plan, days[0], period=None if day_only else slots[0].period)
                response = render(request, "training/schedule_saved.html", {"plan": plan, "next_day": following["day"] if following else None, "next_query": following["query"] if following else "", "submitted": isinstance(result, TrainingScheduleChange)})
                response["HX-Trigger"] = "scheduleChanged"
                moves_rows = any(
                    change["before"].get("date") != change["after"].get("date")
                    or change["before"].get("period") != change["after"].get("period")
                    for change in payload
                )
                if moves_rows or len(days) != 1:
                    return response
                return row_updates(request, response, plan, [slot.pk for slot in slots], [day.pk for day in days])
            return _success(request, plan, "调整申请已提交，批准前原安排保持不变。" if isinstance(result, TrainingScheduleChange) else "排班已保存。")
    return render(
        request,
        "training/schedule_edit.html",
        {
            "plan": plan,
            "days": days,
            "day_forms": day_forms,
            "slot_id": slot_id,
            "day_only": day_only,
            "slot_forms": slot_forms,
            "unified_form": unified_form,
            "disabled_periods": [label for value, label in TrainingScheduleSlot.Period.choices if value not in {slot.period for slot in slots}] if day_only else [],
            "reset_query": f"days={days[0].pk}&day_only=1" if day_only else f"days={days[0].pk}&slot={slot_id}",
            "error": error,
            "entry_filters": filters_for(request).urlencode(),
            "editor_suffix": editor_suffix(filters_for(request)),
            "reason": source.get("reason", ""),
            "show_reason": bool(plan.schedule_published_at) and any(service.was_filled(obj) for obj in [*editable_days, *slots]),
            "is_fragment": bool(request.htmx),
        },
    )


@require_POST
def review(request, pk):
    change = get_object_or_404(TrainingScheduleChange, pk=pk)
    get_plan(request.user, change.training_plan_id)
    if request.POST.get("decision") not in {"approve", "reject"}:
        return _error(request, change.training_plan, ValidationError("请选择批准或驳回。"))
    try:
        service.review_change(
            change, request.user, approve=request.POST["decision"] == "approve", note=request.POST.get("note", "")
        )
    except ValidationError as exc:
        return _error(request, change.training_plan, exc)
    except IntegrityError:
        return _error(request, change.training_plan, ValidationError("安排冲突，未应用任何调整，请重新申请。"))
    return _success(request, change.training_plan, "审批结果已保存。")


def _slot(user, pk):
    slot = get_object_or_404(TrainingScheduleSlot.objects.select_related("day__training_plan__training_cycle"), pk=pk)
    get_plan(user, slot.day.training_plan_id)
    return slot


@require_http_methods(["GET", "POST"])
def task_edit(request, slot_pk=None, pk=None):
    task = get_object_or_404(visible_training_tasks_for(request.user), pk=pk) if pk else None
    if task and not task.schedule_slot_id:
        if not service.task_manager(request.user, task.training_plan) or not request.user.has_perm(
            "training.change_trainingtask"
        ):
            raise Http404
        return redirect("training:legacy_attach", pk=task.pk)
    slot = _slot(request.user, task.schedule_slot_id if task else slot_pk)
    if not service.can_fill(request.user, slot, create=task is None):
        raise PermissionDenied
    navigation = {"entry_filters": filters_for(request).urlencode(), "editor_suffix": editor_suffix(filters_for(request))}
    initial = {}
    if not task and request.GET.get("skill", "").isdigit():
        initial["skills"] = [int(request.GET["skill"])]
    form = SlotTaskForm(request.POST if request.method == "POST" else None, request.FILES if request.method == "POST" else None, instance=task, slot=slot, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            values = dict(form.cleaned_data)
            values["skills"] = list(values["skills"].values_list("pk", flat=True))
            values["competitors"] = list(values["competitors"].values_list("pk", flat=True))
            if task and "assignment_configured" not in request.POST:
                # 精简提交仅更新明确提供的字段，不能清空原技能或重取全体名单。
                values = {key: value for key, value in values.items() if key in request.POST or key in request.FILES}
            result = service.save_slot_task(slot, request.user, values, task=task, publish=request.POST.get("action") == "publish")
            if isinstance(result, TrainingScheduleChange):
                return _success(request, slot.day.training_plan, "任务调整申请已提交，审批前原内容保持不变。")
            task = result
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if request.htmx:
                form = SlotTaskForm(instance=task, slot=slot)
                response = render(
                    request,
                    "training/slot_task_form.html",
                    {
                        **navigation,
                        "next_entry": next_entry(request, slot.day.training_plan, slot.day, period=slot.period, task=True),
                        "form": form,
                        "slot": slot,
                        "task": task,
                        "plan": slot.day.training_plan,
                        "is_fragment": True,
                        "saved": True,
                        "editor_target": request.headers.get("HX-Target", "task-editor"),
                    },
                )
                response["HX-Trigger"] = "scheduleChanged"
                return row_updates(request, response, slot.day.training_plan, [slot.pk])
            return _success(request, slot.day.training_plan, "任务已保存。")
    return render(
        request,
        "training/slot_task_form.html",
        {**navigation, "form": form, "slot": slot, "task": task, "plan": slot.day.training_plan, "is_fragment": bool(request.htmx), "editor_target": request.headers.get("HX-Target", "task-editor")},
    )


@require_POST
def task_action(request, pk):
    task = get_object_or_404(visible_training_tasks_for(request.user), pk=pk)
    try:
        if request.POST.get("action") == "publish":
            service.save_slot_task(task.schedule_slot, request.user, {"reason": request.POST.get("reason", "")}, task=task, publish=True)
        elif request.POST.get("action") == "cancel":
            service.cancel_task(task, request.user, request.POST.get("reason", ""))
        elif request.POST.get("action") == "assign":
            ids = request.POST.getlist("competitors")
            if any(not value.isdigit() for value in ids):
                raise ValidationError("选手名单不正确。")
            service.assign_competitors(task, request.user, selected={int(value) for value in ids}, reason=request.POST.get("reason", ""))
        else:
            raise ValidationError("不支持的任务操作。")
    except ValidationError as exc:
        return _error(request, task.training_plan, exc)
    response = _success(request, task.training_plan, "任务操作已完成。")
    return row_updates(request, response, task.training_plan, [task.schedule_slot_id])


@require_http_methods(["GET", "POST"])
def clear_slot_tasks(request, pk):
    from django.core import signing
    from django.db import transaction
    slot = _slot(request.user, pk)
    if not service.can_fill(request.user, slot):
        raise PermissionDenied
    plan = slot.day.training_plan
    tasks = list(slot.tasks.exclude(status="cancelled").order_by("pk"))
    state = {"user": request.user.pk, "slot": slot.pk, "revision": slot.revision, "tasks": [[task.pk, task.updated_at.isoformat()] for task in tasks]}
    if request.method == "POST":
        try:
            data = signing.loads(request.POST.get("token", ""), salt="training.clear_tasks", max_age=600)
            with transaction.atomic():
                service.TrainingPlan.objects.select_for_update().get(pk=plan.pk)
                current = type(slot).objects.select_for_update().get(pk=slot.pk)
                latest = list(current.tasks.exclude(status="cancelled").order_by("pk").values_list("pk", "updated_at"))
                if data != state or current.revision != data["revision"] or [[pk, updated.isoformat()] for pk, updated in latest] != data["tasks"]:
                    raise ValidationError("任务或排班已经变化，请重新预览。")
                pending = False
                for task in tasks:
                    result = service.cancel_task(task, request.user, request.POST.get("reason", ""))
                    pending = pending or isinstance(result, TrainingScheduleChange)
            return _success(request, plan, "任务取消申请已提交审批。" if pending else "任务内容已取消，排班及完整历史保留。")
        except (signing.BadSignature, ValidationError) as exc:
            return _error(request, plan, ValidationError(str(exc)))
    return render(request, "training/slot_tasks_clear.html", {"slot": slot, "plan": plan, "tasks": tasks, "token": signing.dumps(state, salt="training.clear_tasks"), "is_fragment": bool(request.htmx)})


@require_http_methods(["GET", "POST"])
def task_skills(request, pk):
    task = get_object_or_404(
        visible_training_tasks_for(request.user).select_related("schedule_slot__day__training_plan"), pk=pk
    )
    allowed = (
        service.can_fill(request.user, task.schedule_slot, skills_only=True)
        if task.schedule_slot_id
        else service.task_manager(request.user, task.training_plan)
        and request.user.has_perm("training.change_trainingtask")
    )
    if not allowed:
        raise PermissionDenied
    form = SkillCorrectionForm(request.POST if request.method == "POST" else None, task=task)
    if request.method == "POST" and form.is_valid():
        try:
            result = service.set_task_skills(task, request.user, list(form.cleaned_data["skills"].values_list("pk", flat=True)), reason=form.cleaned_data.get("reason", ""))
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            response = _success(request, task.training_plan, "技能关联调整申请已提交。" if isinstance(result, TrainingScheduleChange) else "技能关联已更新，修改记录已保留。")
            return row_updates(request, response, task.training_plan, [task.schedule_slot_id])
    return render(
        request,
        "training/task_skills.html",
        {"form": form, "task": task, "plan": task.training_plan, "is_fragment": bool(request.htmx)},
    )


@require_GET
def task_competitor_search(request, pk):
    slot = _slot(request.user, pk)
    if not (service.can_fill(request.user, slot) or service.can_fill(request.user, slot, create=True)):
        raise PermissionDenied
    q = request.GET.get("q", "").strip()[:100]
    try:
        page = max(1, min(int(request.GET.get("page", 1)), 10000))
    except ValueError:
        page = 1
    users = (
        slot.day.training_plan.participants.filter(is_active=True)
        .select_related("user")
        .order_by("user__last_name", "user__first_name", "user_id")
    )
    if q:
        users = users.filter(
            Q(user__username__icontains=q) | Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
        )
    else:
        users = users.none()
    rows = list(users[(page - 1) * 20 : page * 20 + 1])
    return JsonResponse(
        {
            "results": [{"id": member.user_id, "label": get_user_display_name(member.user)} for member in rows[:20]],
            "has_more": len(rows) > 20,
        }
    )


@require_http_methods(["GET", "POST"])
def legacy_attach(request, pk):
    task = get_object_or_404(visible_training_tasks_for(request.user), pk=pk)
    plan = get_plan(request.user, task.training_plan_id)
    if not service.task_manager(request.user, plan) or not request.user.has_perm("training.change_trainingtask"):
        raise PermissionDenied

    class AttachForm(forms.Form):
        slot = forms.ModelChoiceField(
            label="目标排班时段", queryset=plan_slots(plan, request.user).filter(is_configured=True, kind__in=service.ACTIVE_KINDS)
        )

    form = AttachForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            service.attach_legacy_task(task, form.cleaned_data["slot"], request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return _success(request, plan, "历史任务已接入排班，原执行与日志关联保留。")
    return render(
        request,
        "training/task_skills.html",
        {"form": form, "task": task, "plan": plan, "is_fragment": bool(request.htmx)},
    )


@require_GET
def export_plan(request, pk):
    plan = get_plan(request.user, pk)
    if not request.user.has_perm("training.view_trainingtask"):
        raise PermissionDenied
    if not plan.schedule_published_at:
        return _error(request, plan, ValidationError("排班发布后才能导出正式计划。"))
    from .schedule_export import build_plan_workbook
    from django.utils.http import content_disposition_header

    response = HttpResponse(
        build_plan_workbook(plan, request.user), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = content_disposition_header(True, f"{plan.title}.xlsx")
    return response


@require_GET
def legacy_task_list(request):
    return redirect("training:plan_list")


@require_GET
def legacy_task_create(request):
    if not request.user.has_perm("training.add_trainingtask"):
        raise PermissionDenied
    plans = service.visible_plans(request.user)
    selected = plans.filter(pk=request.GET["plan"]).first() if request.GET.get("plan", "").isdigit() else None
    slots = plan_slots(selected, request.user) if selected else []
    slots = [slot for slot in slots if service.can_fill(request.user, slot, create=True)]
    return render(
        request,
        "training/task_select_slot.html",
        {"plans": plans, "slots": slots, "selected": selected, "skill_id": request.GET.get("skill", "")},
    )
