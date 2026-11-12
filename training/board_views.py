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
from .daily_progress import training_day_is_available, training_day_url, training_upload_url
from .models import TaskExecution, TrainingLog, TrainingPlanStaff, TrainingProgress, TrainingScheduleSlot, TrainingTask
from .process import personal_tasks_for
from .scheduling import visible_plans
from .selectors import visible_task_executions_for, visible_training_tasks_for


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
        if not all_dates:
            tasks = tasks.filter(planned_date=day)
            if personal is not None:
                personal = personal.filter(date=day)
        if user.has_perm("training.view_taskexecution"):
            executions = visible_task_executions_for(user, active_executions()) if coach_view else own_executions
        else:
            executions = own_executions.none()
        if not coach_view and user.has_perm("training.view_trainingprogress"):
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
            task.period_key = period_order(task)[1:]
            if coach_view:
                task.board_statuses = Counter(item.get_status_display() for item in task.board_executions).items()
            elif task.board_executions:
                task.board_execution = task.board_executions[0]
                records = getattr(task.board_execution, "checklist_records", ())
                record = next((record for record in records if record.training_date == task.planned_date), None)
                counts = completion_counts(record)
                if counts:
                    done, total = counts
                    label = "全部完成" if done == total else "部分完成" if done else "未执行"
                    task.completion = f"{label} · {done}/{total} · 已填报"
                elif task.board_execution.status == TaskExecution.Status.ASSIGNED and task.schedule_slot_id:
                    task.completion = f"未执行 · 0/{len(task.subtasks) or 1}"
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
            actions = []
            cycle_ids = dict.fromkeys(task.training_plan.training_cycle_id for task in group if task.schedule_slot_id)
            for cycle_id in cycle_ids:
                member = members.get(cycle_id)
                available = training_day_is_available(member, current_day, today)
                log_id = submitted.get((cycle_id, current_day))
                if not available and not (log_id and can_view_log):
                    continue
                cycle = member.training_cycle
                actions.append({
                    "cycle": cycle.name if len(cycle_ids) > 1 else "",
                    "completion": training_day_url("training:daily_progress", cycle_id, current_day)
                    if available and can_view_progress and member.role == member.Role.COMPETITOR and not coach_view else "",
                    "log": training_day_url("training:log_ai_start", cycle_id, current_day)
                    if available and not log_id and can_add_log and can_view_progress else "",
                    "upload": training_upload_url(cycle_id, current_day) if available and not log_id and can_add_log else "",
                    "submitted": reverse("training:log_detail", args=[log_id])
                    if log_id and can_view_log else "",
                })
            date_groups.append({"day": current_day, "tasks": group, "actions": actions})
        context.update(
            tasks=tasks, date_groups=date_groups, coach_view=coach_view, day=day, previous_day=previous_day, next_day=next_day,
            all_dates=all_dates, personal_tasks=personal, personal_plans=own_plans,
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
