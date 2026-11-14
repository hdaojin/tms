"""计划内日程和任务列表，所有任务内容先经统一 selector 收窄。"""

import django_tables2 as tables
from django.db.models import Q
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from core.tables import BaseTable, BaseDateColumn
from accounts.services.users import get_user_display_name, get_user_full_info
from . import scheduling
from .models import TrainingScheduleSlot
from .process import personal_tasks_for
from .selectors import visible_training_tasks_for


class ScheduleDayTable(BaseTable):
    selection = tables.Column(
        empty_values=(),
        verbose_name=mark_safe(
            '<input type="checkbox" class="checkbox checkbox-sm" aria-label="全选当前页可操作时段" data-select-page>'
        ),
        orderable=False,
    )
    date = BaseDateColumn(verbose_name="日期 / 星期", orderable=False)
    early = tables.Column(empty_values=(), verbose_name="早读", orderable=False)
    morning = tables.Column(empty_values=(), verbose_name="上午", orderable=False)
    afternoon = tables.Column(empty_values=(), verbose_name="下午", orderable=False)
    evening = tables.Column(empty_values=(), verbose_name="晚上", orderable=False)

    class Meta(BaseTable.Meta):
        template_name = "training/day_table.html"
        row_attrs = {"id": lambda record: f"entry-day-{record.pk}", "class": lambda record: "bg-base-200/40" if record.is_past else ""}

    def __init__(self, *args, user, plan, **kwargs):
        self.user, self.plan = user, plan
        super().__init__(*args, **kwargs)
        self.columns.hide("selection")

    def render_selection(self, record):
        return format_html_join("", '<label class="flex items-center gap-1 whitespace-nowrap text-xs"><input class="checkbox checkbox-xs" type="checkbox" name="slots" value="{}" data-row-selection>{}</label>',
            ((slot.pk, slot.get_period_display()) for slot in record.matching_slots if slot.is_configured and (slot.can_schedule or slot.can_fill)))

    def render_date(self, record):
        from django.urls import reverse

        label = format_html('<span class="whitespace-nowrap">{} 星期{}</span>', record.date.isoformat(), "一二三四五六日"[record.date.weekday()])
        summary = format_html('<div>{}</div><div class="mt-2 text-sm">值班：{}</div><div class="mt-1 whitespace-pre-wrap text-sm">{}</div>', label, record.duty_label, record.visible_note)
        links = []
        if scheduling.can_schedule(self.user, self.plan) and self.plan.published_at:
            url = reverse("training:schedule_edit", args=[self.plan.pk]) + f"?days={record.pk}&day_only=1{record.editor_suffix}"
            links.append((url, url, "schedule-editor", "编辑全天排班"))
        if record.can_edit_tasks:
            url = reverse("training:day_task_edit", args=[self.plan.pk, record.pk])
            links.append((url, url, "task-editor", "编辑全天任务"))
        return format_html("{}{}", summary, format_html_join(
            "", '<div><a class="link text-xs" href="{}" hx-get="{}" hx-target="#{}">{}</a></div>', links
        ))

    def cell(self, record, period):
        from .schedule_entries import render_slot
        return render_slot(self, record, period)

    def render_early(self, record):
        return self.cell(record, "early")

    def render_morning(self, record):
        return self.cell(record, "morning")

    def render_afternoon(self, record):
        return self.cell(record, "afternoon")

    def render_evening(self, record):
        return self.cell(record, "evening")

    def render_duty(self, record):
        return record.duty_label

    def render_note(self, record):
        return record.visible_note


def plan_context(view, context):
    user, plan = view.request.user, view.object
    tasks = (
        visible_training_tasks_for(user)
        .filter(training_plan=plan)
        .select_related("schedule_slot__primary_domain", "schedule_slot__day")
    )
    filters = view.request.GET
    if query := filters.get("q", "").strip():
        tasks = tasks.filter(title__icontains=query)
    for param, field in (
        ("date", "planned_date"),
        ("period", "schedule_slot__period"),
        ("domain", "schedule_slot__primary_domain_id"),
        ("coach", "schedule_slot__coaches"),
    ):
        value = filters.get(param, "")
        if value:
            if param == "domain" and value in scheduling.SPECIAL_DOMAIN_KINDS:
                tasks = tasks.filter(schedule_slot__kind=scheduling.SPECIAL_DOMAIN_KINDS[value])
            elif param in {"domain", "coach"} and not value.isdecimal():
                tasks = tasks.none()
            elif param == "date":
                from datetime import date

                try:
                    date.fromisoformat(value)
                except ValueError:
                    tasks = tasks.none()
                else:
                    tasks = tasks.filter(**{field: value})
            else:
                tasks = tasks.filter(**{field: value})
    from .schedule_entries import entry_context
    entries = entry_context(view, ScheduleDayTable)
    table, is_tasks = entries["table"], entries["task_tab"]
    staff = scheduling.staff(user, plan)
    from .log_exemptions import ACTIONS as LOG_EXEMPTION_ACTIONS

    history = plan.change_records.exclude(action__in=LOG_EXEMPTION_ACTIONS.values()).select_related("actor", "task")
    if not staff:
        history = history.filter(task__schedule_slot__coaches=user).distinct()
    from .schedule_history import decorate_history

    change_query = plan.schedule_changes.select_related("requested_by", "reviewed_by", "training_plan").prefetch_related("attachments")
    if not staff:
        change_query = change_query.filter(Q(confirmation_users=user) | Q(requested_by=user)).distinct()
    from django.core.paginator import Paginator

    history_page = Paginator(history, 10).get_page(view.request.GET.get("history_page"))
    history, changes = decorate_history(history_page.object_list, change_query[:50])
    from .change_workflow import can_review, next_coach
    from django.contrib.auth import get_user_model
    names = {person.pk: get_user_display_name(person) for person in get_user_model().objects.filter(pk__in={step["user_id"] for change in changes for step in change.confirmations})}
    for change in changes:
        change.training_plan = plan
        change.can_review = can_review(user, change)
        change.waiting_for = names.get(next_coach(change), "计划审批人员或超级管理员")
        for step in change.confirmations:
            step["display_name"] = names.get(step["user_id"], "教练")
    configured_periods = set(TrainingScheduleSlot.Period.values)
    context.update(
        table=table,
        task_tab=is_tasks,
        can_schedule=scheduling.can_schedule(user, plan),
        can_see_management=staff,
        can_manage=scheduling.plan_manager(user, plan),
        can_approve=scheduling.can_approve(user, plan),
        periods=[(value, label) for value, label in TrainingScheduleSlot.Period.choices if value in configured_periods],
        filter_domains=plan.training_cycle.skill_tree_version_links.select_related("technical_domain"),
        filter_coaches=plan.training_cycle.members.filter(role="coach").select_related("user"),
        history=history,
        history_page=history_page,
        changes=changes,
        legacy_tasks=tasks.filter(schedule_slot__isnull=True),
        can_attach=scheduling.task_manager(user, plan) and user.has_perm("training.change_trainingtask"),
        personal_tasks=personal_tasks_for(user).filter(training_plan=plan),
    )
    from django.urls import reverse
    from core.utils.listing import FilterableListMixin

    filter_url = reverse("training:plan_detail", args=[plan.pk])
    domains = [(link.technical_domain_id, link.technical_domain) for link in context["filter_domains"]] + scheduling.SPECIAL_DOMAIN_CHOICES
    coaches = [(member.user_id, get_user_full_info(member.user)) for member in context["filter_coaches"]]
    specs = [
        ("q", "搜索任务或日备注", "search", [], "搜索任务或日备注"),
        ("date_from", "开始日期", "date", [], "从"),
        ("date_to", "结束日期", "date", [], "至"),
        ("period", "时段", "select", context["periods"], ""),
        ("domain", "领域", "select", domains, ""),
        ("coach", "负责教练", "select", coaches, ""),
        ("state", "排班状态", "select", [("pending", "待排班"), ("scheduled", "已排班")], ""),
        ("mine", "负责范围", "select", [("1", "我负责的时段")], ""),
    ]
    context.update(
        list_filter_url=filter_url,
        list_filter_reset_url=f"{filter_url}?tab={'details' if is_tasks else 'schedule'}",
        list_filter_target_id="list-results",
        list_filter_trigger=FilterableListMixin.list_filter_trigger,
        list_filter_hidden_fields=[{"name": "tab", "value": "details" if is_tasks else "schedule"}, {"name": "fragment", "value": "results"}],
        list_filter_controls=[
            {"name": name, "label": label, "type": kind, "value": filters.get(name, ""),
             "placeholder": placeholder, "empty_label": f"全部{label}",
             "choices": [{"value": str(value), "label": str(choice)} for value, choice in choices]}
            for name, label, kind, choices, placeholder in specs
        ],
    )
    context["list_filter_controls"].append({"name": "weekday", "label": "星期", "type": "checkboxes", "values": filters.getlist("weekday"), "choices": [{"value": str(index), "label": "星期" + label} for index, label in enumerate("一二三四五六日")]})
    from django import forms

    options = [("", "请选择操作")]
    if scheduling.can_schedule(user, plan):
        options += [("schedule", "批量排班"), ("copy", "复制排班"), ("clear", "清空排班"), ("unused", "设为不安排")]
    if user.has_perm("training.add_trainingtask"):
        options.append(("tasks", "批量填写任务"))
    bulk_form = forms.Form()
    bulk_form.fields["operation"] = forms.ChoiceField(
        label="操作",
        choices=options,
        widget=forms.Select(attrs={"class": "select select-sm", "data-bulk-operation": ""}),
    )
    context["operation_field"] = bulk_form["operation"]
    context.update(entries)
    return context
