from collections import Counter, defaultdict
from datetime import date, timedelta

from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from django.views.generic import TemplateView

from core.utils.mixins import TitleMixin

from .board_selectors import public_board_plans
from .checklists import completion_counts
from .daily_progress import displayed_execution_status
from .daily_progress import LOG_COMPLETION_REQUIRED, log_completion_pending, training_day_is_available, training_day_url, training_upload_url
from .models import TaskExecution, TrainingLog, TrainingPlanStaff, TrainingProgress, TrainingScheduleSlot, TrainingTask
from .process import personal_tasks_for
from .scheduling import visible_plans
from .selectors import visible_task_executions_for, visible_training_tasks_for
from .training_return import with_training_return


PERIOD_ORDER = {period: index for index, period in enumerate(TrainingScheduleSlot.Period.values)}
PUBLISHED_SCHEDULE = Q(
    training_plan__published_at__isnull=False,
    training_plan__schedule_published_at__isnull=False,
)
PUBLISHED_TASK = Q(status=TrainingTask.Status.PUBLISHED) & (
    Q(schedule_slot__isnull=True) | PUBLISHED_SCHEDULE
)


def active_executions():
    return TaskExecution.objects.filter(revoked_at__isnull=True).exclude(status=TaskExecution.Status.CANCELLED)


def task_cards(queryset):
    return queryset.select_related("schedule_slot", "training_plan").prefetch_related(
        "domain_links__technical_domain",
        "skill_links", "attachments",
    ).order_by("planned_date", "schedule_slot__starts_at", "order", "pk")


def period_order(task):
    period = task.schedule_slot.period if task.schedule_slot else None
    start = task.schedule_slot.starts_at if task.schedule_slot else None
    end = task.schedule_slot.ends_at if task.schedule_slot else None
    return (task.planned_date, PERIOD_ORDER.get(period, len(PERIOD_ORDER)), str(start), str(end))


class MyTrainingView(TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "training/my_training.html"
    title = "我的训练"
    permission_required = "training.view_trainingtask"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        raw_date = self.request.GET.get("date")
        try:
            day = date.fromisoformat(raw_date) if raw_date else timezone.localdate()
            previous_day, next_day = day - timedelta(days=1), day + timedelta(days=1)
        except (ValueError, OverflowError) as exc:
            raise Http404("无效的训练日期") from exc
        all_dates = self.request.GET.get("scope") == "all"

        own_executions = active_executions().filter(user=user)
        visible = visible_training_tasks_for(user)
        own_tasks = visible.filter(pk__in=own_executions.values("training_task_id")).filter(
            Q(schedule_slot__isnull=True) | (PUBLISHED_SCHEDULE & Q(status=TrainingTask.Status.PUBLISHED)),
        ).exclude(status=TrainingTask.Status.CANCELLED)
        coach_relation = Q(schedule_slot__coaches=user) | Q(schedule_slot__isnull=True, coach_links__user=user)
        coach_tasks = visible.filter(coach_relation, PUBLISHED_TASK).distinct()

        plans = visible_plans(user)
        own_plans = plans.filter(participants__user=user, participants__is_active=True)
        current_plans = plans.filter(start_date__lte=day, end_date__gte=day)
        is_competitor = own_plans.filter(pk__in=current_plans).exists() or own_tasks.filter(planned_date=day).exists()
        is_coach = coach_tasks.filter(planned_date=day).exists() or current_plans.filter(
            Q(staff_members__user=user, staff_members__role=TrainingPlanStaff.Role.COACH, staff_members__is_active=True)
            | Q(schedule_days__slots__coaches=user)
        ).exists()
        if not is_competitor and not is_coach:
            is_coach = coach_tasks.exists() and not (own_tasks.exists() or own_plans.exists())
        coach_view = is_coach and not is_competitor

        tasks = coach_tasks if coach_view else own_tasks
        personal = personal_tasks_for(user).filter(user=user) if not coach_view else None
        related_plans = plans.filter(pk__in=tasks.order_by().values("training_plan_id"))
        if not coach_view:
            related_plans = plans.filter(
                Q(pk__in=related_plans.values("pk")) | Q(pk__in=own_plans.values("pk"))
                | Q(pk__in=personal.order_by().values("training_plan_id"))
            )
        plan_choices = list(related_plans.order_by("-start_date", "pk"))
        requested_plan = self.request.GET.get("plan")
        selected_plan = next((plan for plan in plan_choices if str(plan.pk) == requested_plan), None)
        if selected_plan is None:
            selected_plan = next((plan for plan in plan_choices if plan.start_date <= day <= plan.end_date), None)
        if selected_plan is None and plan_choices:
            selected_plan = plan_choices[0]
        if selected_plan:
            tasks = tasks.filter(training_plan=selected_plan)
            if personal is not None:
                personal = personal.filter(training_plan=selected_plan)
        origin = {"date": day.isoformat()}
        if all_dates:
            origin["scope"] = "all"
        if selected_plan:
            origin["plan"] = selected_plan.pk
        if personal is not None:
            personal = personal.select_related("domain")
            personal = list(personal.filter(date=day) if not all_dates else personal)
            for item in personal:
                item.training_url = with_training_return(reverse("training:personal_detail", args=[item.pk]), origin)
        if not all_dates:
            tasks = tasks.filter(planned_date=day)
        if user.has_perm("training.view_taskexecution"):
            executions = visible_task_executions_for(user, active_executions()) if coach_view else own_executions
        else:
            executions = own_executions.none()
        if user.has_perm("training.view_trainingprogress"):
            executions = executions.prefetch_related(Prefetch(
                "progress_records", queryset=TrainingProgress.objects.filter(checklist__isnull=False),
                to_attr="checklist_records",
            ))
        tasks = sorted(
            task_cards(tasks).prefetch_related(Prefetch("executions", queryset=executions, to_attr="board_executions")),
            key=period_order,
        )
        dated_tasks = defaultdict(list)
        for task in tasks:
            dated_tasks[task.planned_date].append(task)
            task.training_url = with_training_return(reverse("training:task_detail", args=[task.pk]), origin)
            task.period_key = period_order(task)[1:]
            if coach_view:
                task.board_statuses = Counter(
                    displayed_execution_status(item, task.schedule_slot, timezone.now())
                    for item in task.board_executions
                ).items()
            elif task.board_executions:
                task.board_execution = task.board_executions[0]
                records = getattr(task.board_execution, "checklist_records", ())
                record = next((record for record in records if record.training_date == task.planned_date), None)
                counts = completion_counts(record)
                if counts:
                    done, total = counts
                    label = "已完成" if done == total else "部分完成" if done else "未完成"
                    task.completion = f"{label} · {done}/{total} · 已填报"
                else:
                    task.completion = displayed_execution_status(task.board_execution, task.schedule_slot, timezone.now())
                task.board_counts = counts
                task.board_checklist = tuple(item["done"] for item in record.checklist) if counts else None
        members = {member.training_cycle_id: member for member in user.training_cycle_memberships.select_related(
            "training_cycle",
        )}
        today = timezone.localdate()
        can_view_progress = user.has_perms(("training.view_taskexecution", "training.view_trainingprogress"))
        can_add_log = user.has_perm("training.add_traininglog")
        can_view_log = user.has_perm("training.view_traininglog")
        submitted = {
            (cycle_id, log_day): pk
            for cycle_id, log_day, pk in TrainingLog.objects.filter(
                author=user, training_cycle_id__in=members, training_date__in=dated_tasks,
            ).values_list("training_cycle_id", "training_date", "pk")
        }
        date_groups = []
        for current_day, group in dated_tasks.items():
            rows = {}
            for task in group:
                domains = tuple(sorted(link.technical_domain.name for link in task.domain_links.all()))
                domain_ids = tuple(sorted(link.technical_domain_id for link in task.domain_links.all()))
                key = (domain_ids, task.title, task.schedule_slot.kind if task.schedule_slot_id else task.pk)
                row = rows.setdefault(key, {"task": task, "domains": domains, "periods": []})
                row["periods"].append(task)
            for row in rows.values():
                periods = row["periods"]
                content = min(periods, key=lambda task: task.pk)
                row["all_day"] = {"morning", "afternoon"} <= {
                    task.schedule_slot.period for task in periods if task.schedule_slot_id
                }
                row["subtask_count"] = len(content.subtasks)
                row["skill_count"] = len(content.skill_links.all())
                row["attachment_count"] = (
                    len(content.attachments.all()) if user.has_perm("training.view_trainingtaskattachment") else 0
                )
                results = []
                for task in periods:
                    if coach_view and user.has_perm("training.view_taskexecution"):
                        result = " · ".join(
                            f"{label} {count} 人" for label, count in sorted(task.board_statuses)
                        ) or "暂无可查看的执行分配"
                    elif getattr(task, "board_execution", None):
                        result = getattr(task, "completion", "") or task.board_execution.get_status_display()
                    else:
                        result = "—"
                    results.append((task.schedule_slot.get_period_display() if task.schedule_slot_id else "", result))
                row["completion"] = results if len({result for _, result in results}) > 1 else [("", results[0][1])]
                if row["all_day"] and coach_view and len(row["completion"]) > 1:
                    row["completion"] = [("", "各时段完成情况不同")]
                if row["all_day"] and not coach_view and all(getattr(task, "board_execution", None) for task in periods):
                    counts = [task.board_counts for task in periods]
                    now = timezone.now()
                    if any(counts):
                        result = results[0][1] if len({task.board_checklist for task in periods}) == 1 else "完成情况待统一"
                    elif all(task.schedule_slot.ends_at and now >= task.schedule_slot.ends_at for task in periods):
                        result = "未完成"
                    elif any(
                        task.board_execution.viewed_at and task.schedule_slot.starts_at and now >= task.schedule_slot.starts_at
                        or task.board_execution.status == TaskExecution.Status.IN_PROGRESS
                        for task in periods
                    ):
                        result = "进行中"
                    else:
                        result = "未开始"
                    row["completion"] = [("", result)]
            actions = []
            cycle_ids = dict.fromkeys(task.training_plan.training_cycle_id for task in group if task.schedule_slot_id)
            for cycle_id in cycle_ids:
                member = members.get(cycle_id)
                available = training_day_is_available(member, current_day, today)
                log_id = submitted.get((cycle_id, current_day))
                if not available and not (log_id and can_view_log):
                    continue
                cycle = member.training_cycle
                pending = available and not log_id and can_add_log and log_completion_pending(user, cycle_id, current_day)
                actions.append({
                    "cycle": cycle.name if len(cycle_ids) > 1 else "",
                    "log_blocked": LOG_COMPLETION_REQUIRED if pending else "",
                    "completion": training_day_url("training:daily_progress", cycle_id, current_day)
                    if available and can_view_progress and member.role == member.Role.COMPETITOR and not coach_view else "",
                    "log": training_day_url("training:log_ai_start", cycle_id, current_day)
                    if available and not log_id and can_add_log and can_view_progress else "",
                    "upload": training_upload_url(cycle_id, current_day) if available and not log_id and can_add_log else "",
                    "submitted": reverse("training:log_detail", args=[log_id])
                    if log_id and can_view_log else "",
                })
            for action in actions:
                for key in ("completion", "log", "upload", "submitted"):
                    if action[key]:
                        action[key] = with_training_return(action[key], origin)
            date_groups.append({"day": current_day, "rows": rows.values(), "actions": actions})
        context.update(
            tasks=tasks, date_groups=date_groups, coach_view=coach_view, day=day, previous_day=previous_day, next_day=next_day,
            all_dates=all_dates, personal_tasks=personal, plan_choices=plan_choices, selected_plan=selected_plan,
            personal_plans=own_plans.filter(pk__in=current_plans, pk=selected_plan.pk) if selected_plan else own_plans.none(),
        )
        return context


@login_not_required
@never_cache
@require_safe
def training_board(request):
    now = timezone.now()
    today = timezone.localdate(now, timezone.get_default_timezone())
    template = "training/training_board.html"
    if request.GET.get("fragment") == "1":
        template += "#screen_content"
    return render(request, template, {
        "today": today, "plans": public_board_plans(today=today, now=now), "title": "今日训练任务",
    })
