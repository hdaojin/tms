"""两种排班视图共用的可见条目、筛选和日期分页。"""

from datetime import date, timedelta

import django_tables2 as tables
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from core.tables import BaseTable, BaseDateColumn
from accounts.services.users import get_user_display_name
from . import scheduling
from .models import TrainingScheduleSlot
from .selectors import visible_training_tasks_for


def slot_state(slot):
    return ("已排班", "badge-success") if scheduling.slot_complete(slot) else ("待排班", "badge-info")


class ScheduleDetailTable(BaseTable):
    selection = tables.Column(
        empty_values=(),
        verbose_name=mark_safe(
            '<input type="checkbox" class="checkbox checkbox-sm" aria-label="全选当前页可操作时段" data-select-page>'
        ),
        orderable=False,
    )
    date = BaseDateColumn(accessor="day__date", verbose_name="日期", orderable=False)
    period = tables.Column(verbose_name="时段", orderable=False)
    domain = tables.Column(
        empty_values=(), verbose_name="领域", orderable=False, attrs={"td": {"class": "min-w-28 whitespace-nowrap text-center"}}
    )
    tasks = tables.TemplateColumn(template_name="training/entry_tasks.html", verbose_name="训练任务", orderable=False)
    coaches = tables.Column(
        empty_values=(), verbose_name="负责教练", orderable=False, attrs={"td": {"class": "min-w-40 text-center"}}
    )
    duty = tables.Column(empty_values=(), verbose_name="值班人员", orderable=False)
    note = tables.Column(
        empty_values=(),
        verbose_name="备注",
        orderable=False,
        attrs={"td": {"class": "min-w-40 whitespace-pre-wrap text-center"}},
    )

    class Meta(BaseTable.Meta):
        row_attrs = {"id": lambda record: f"entry-slot-{record.pk}", "class": lambda record: record.day.detail_row_class}

    def render_selection(self, record):
        if record.is_configured and (record.can_schedule or record.can_fill):
            return format_html(
                '<input class="checkbox checkbox-sm" type="checkbox" name="slots" value="{}" data-row-selection aria-label="选择时段">',
                record.pk,
            )
        return "—"

    def render_period(self, record):
        return record.get_period_display() + ("（未启用）" if not record.is_configured else "")

    def render_domain(self, record):
        return record.domain_label if record.content_visible else "—"

    def render_coaches(self, record):
        return record.coach_label if record.content_visible else "—"

    def render_duty(self, record):
        return record.day.duty_label

    def render_note(self, record):
        return record.day.visible_note


def entry_context(view, day_table, *, matching_only=False):
    user, plan, params = view.request.user, view.object, view.request.GET
    from .entry_navigation import filters_for, editor_suffix
    suffix = editor_suffix(filters_for(view.request))
    internal = scheduling.staff(user, plan)
    visible_tasks = (
        visible_training_tasks_for(user)
        .filter(training_plan=plan)
        .exclude(status="cancelled")
        .only("pk", "schedule_slot_id", "training_plan_id", "title", "status", "order")
        .order_by("order", "pk")
    )
    slots = TrainingScheduleSlot.objects.select_related("primary_domain").prefetch_related(
        "coaches", "domains", Prefetch("tasks", queryset=visible_tasks, to_attr="visible_tasks")
    )
    days = plan.schedule_days.prefetch_related("duty_coaches", Prefetch("slots", queryset=slots)).order_by(
        "date"
    )
    active_filter = any(
        params.get(key)
        for key in ("q", "date", "date_from", "date_to", "period", "domain", "coach", "state", "mine", "weekday")
    )
    weekdays = params.getlist("weekday")
    valid = all(value in {str(index) for index in range(7)} for value in weekdays)
    for key in ("date", "date_from", "date_to"):
        if params.get(key):
            try:
                date.fromisoformat(params[key])
            except ValueError:
                valid = False
    today = timezone.localdate()
    result = []
    for day in days:
        day.training_plan = plan
        day.editor_suffix = suffix
        day.is_past = day.date < today
        day.week_past = day.date - timedelta(days=day.date.weekday()) + timedelta(days=6) < today
        day.duty_label = (
            (
                "全体"
                if day.duty_all
                else format_html_join(
                    "、",
                    '<span class="whitespace-nowrap">{}</span>',
                    ((get_user_display_name(person),) for person in day.duty_coaches.all()),
                )
                or "—"
            )
            if internal or plan.schedule_published_at
            else "—"
        )
        day.visible_note = day.note if internal or plan.schedule_published_at else ""
        day.week_start = (day.date - timedelta(days=day.date.weekday())).isoformat()
        matches = []
        for slot in sorted(day.slots.all(), key=lambda item: TrainingScheduleSlot.Period.values.index(item.period)):
            slot.day = day
            slot.editor_suffix = suffix
            coach_ids = {person.pk for person in slot.coaches.all()}
            slot.content_visible = (
                internal or user.pk in coach_ids or bool(plan.schedule_published_at and slot.visible_tasks)
            )
            slot.domain_label = (
                str(slot.primary_domain) if slot.primary_domain_id else {"general": "其他", "rest": "休息", "unused": "不安排"}.get(slot.kind, "—")
            )
            slot.coach_label = (
                format_html_join(
                    "、",
                    '<span class="whitespace-nowrap">{}</span>',
                    (
                        (get_user_display_name(person),)
                        for person in slot.coaches.all()
                    ),
                )
                or "—"
            )
            slot.state_label, slot.state_class = slot_state(slot)
            slot.can_schedule = bool(plan.published_at and scheduling.can_schedule(user, plan))
            slot.can_fill = scheduling.can_fill(user, slot, create=True)
            for task in slot.visible_tasks:
                task.can_edit = task.status != "cancelled" and scheduling.can_fill(user, slot)
            match = valid and (not weekdays or str(day.date.weekday()) in weekdays)
            for key, value in (
                ("date", day.date.isoformat()),
                ("period", slot.period),
                (
                    "domain",
                    str(slot.primary_domain_id)
                    if slot.primary_domain_id
                    else {"general": "other", "rest": "rest", "unused": "unused"}.get(slot.kind, ""),
                ),
            ):
                if params.get(key) and params[key] != value:
                    match = False
            if (
                params.get("date_from")
                and day.date.isoformat() < params["date_from"]
                or params.get("date_to")
                and day.date.isoformat() > params["date_to"]
            ):
                match = False
            if params.get("coach") and params["coach"] not in {str(pk) for pk in coach_ids}:
                match = False
            if params.get("mine") and user.pk not in coach_ids:
                match = False
            state = "scheduled" if scheduling.slot_complete(slot) else "pending"
            if params.get("state") and params["state"] != state:
                match = False
            query = params.get("q", "").strip().casefold()
            if (
                query
                and query not in day.visible_note.casefold()
                and not any(query in task.title.casefold() for task in slot.visible_tasks)
            ):
                match = False
            if active_filter and not slot.content_visible:
                match = False
            slot.matches_filter = match
            if not slot.content_visible:
                slot.visible_tasks = []
            if match:
                matches.append(slot)
        day.matching_slots = matches
        if matches:
            result.append(day)
    if matching_only:
        return result
    page = Paginator(result, 31).get_page(params.get("page"))
    for index, day in enumerate(page):
        day.detail_row_class = (
            ("bg-base-300/60" if index % 2 else "bg-base-200/60")
            if day.is_past
            else ("bg-base-200/30" if index % 2 else "")
        )
        week_days = [other.date for other in page if other.week_start == day.week_start]
        day.week_label = f"{min(week_days)} 至 {max(week_days)}（本页）"
    details = params.get("tab") in {"tasks", "details"}
    table = (
        ScheduleDetailTable([slot for day in page for slot in day.matching_slots])
        if details
        else day_table(list(page), user=user, plan=plan)
    )
    table.request = view.request
    can_bulk = False
    table.columns.hide("selection")
    table.order_by = ()
    return {
        "table": table,
        "page_obj": page,
        "task_tab": details,
        "entry_days": list(page),
        "matching_count": sum(len(day.matching_slots) for day in result),
        "entry_filters_active": active_filter,
        "can_bulk_entries": can_bulk,
        "can_bulk_tasks": False,
    }


def render_slot(table, day, period):
    slot = next((slot for slot in day.slots.all() if slot.period == period), None)
    if slot is None:
        return "待整理"
    if slot.is_configured and slot.matches_filter and not slot.content_visible:
        return ""
    return render_to_string(
        "training/schedule_cell.html",
        {"slot": slot, "plan": table.plan, "can_fill": slot.can_fill, "can_schedule": slot.can_schedule},
        request=table.request,
    )
