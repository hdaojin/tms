from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone

from .models import TaskExecution, TrainingCycle, TrainingCycleMember, TrainingLog, TrainingProgress, TrainingTask
from .services import validate_new_log


def validate_training_day(user, cycle, day):
    member = cycle.members.filter(user=user).first()
    if not user.is_active or member is None:
        raise PermissionDenied
    validate_new_log(
        TrainingLog(author=user, training_cycle=cycle, training_date=day), backfill=day < timezone.localdate()
    )
    return member


def available_cycles(user, day):
    members = TrainingCycleMember.objects.filter(user=user)
    if day == timezone.localdate():
        members = members.filter(is_current=True, training_cycle__status=TrainingCycle.Status.ACTIVE)
    else:
        members = members.filter(
            training_cycle__status__in=[TrainingCycle.Status.ACTIVE, TrainingCycle.Status.COMPLETED]
        )
    return TrainingCycle.objects.filter(pk__in=members.values("training_cycle_id"))


def scheduled_tasks(cycle, day):
    return TrainingTask.objects.filter(
        training_plan__training_cycle=cycle,
        training_plan__published_at__isnull=False,
        training_plan__schedule_published_at__isnull=False,
        schedule_slot__day__date=day,
        schedule_slot__is_configured=True,
        status=TrainingTask.Status.PUBLISHED,
    ).exclude(schedule_slot__kind__in=["pending", "rest", "unused"])


def active_executions():
    return TaskExecution.objects.filter(revoked_at__isnull=True).exclude(status=TaskExecution.Status.CANCELLED)


def daily_executions(user, cycle, day):
    return (
        active_executions()
        .filter(user=user, training_task__in=scheduled_tasks(cycle, day))
        .select_related("training_task__training_plan", "training_task__schedule_slot")
        .prefetch_related(
            "training_task__domain_links__technical_domain",
            Prefetch(
                "progress_records",
                TrainingProgress.objects.filter(training_date=day).prefetch_related("attachments"),
                to_attr="daily_records",
            ),
            Prefetch(
                "progress_records", TrainingProgress.objects.filter(training_date__isnull=True), to_attr="older_records"
            ),
        )
        .order_by(
            "training_task__training_plan_id", "training_task__schedule_slot__starts_at", "training_task__order", "pk"
        )
    )


def validate_daily_execution(execution, user, day):
    cycle = execution.training_task.training_plan.training_cycle
    member = validate_training_day(user, cycle, day)
    if (
        member.role != TrainingCycleMember.Role.COMPETITOR
        or execution.user_id != user.pk
        or not daily_executions(user, cycle, day).filter(pk=execution.pk).exists()
    ):
        raise PermissionDenied


def has_text(record):
    return bool(record and (record.completed.strip() or record.problems.strip()))


def day_fingerprint(executions):
    from .checklists import checklist_items

    return [
        [
            row.pk,
            checklist_items(row.training_task),
            row.daily_records[0].updated_at.isoformat() if row.daily_records else None,
        ]
        for row in executions
    ]


def save_day(user, cycle, day, fingerprint, entries, *, problems, images):
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from . import process
    from .checklists import checklist_items
    from .models import TrainingPlan, TrainingStateChange

    written_files = []
    try:
        with transaction.atomic():
            member = validate_training_day(user, cycle, day)
            if member.role != TrainingCycleMember.Role.COMPETITOR:
                raise PermissionDenied
            plans = TrainingPlan.objects.filter(training_cycle=cycle, start_date__lte=day, end_date__gte=day)
            list(plans.select_for_update().order_by("pk").values_list("pk", flat=True))
            tasks = scheduled_tasks(cycle, day)
            list(
                TrainingTask.objects.select_for_update()
                .filter(pk__in=tasks)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            assignments = active_executions().filter(user=user, training_task__in=tasks)
            list(assignments.select_for_update().order_by("pk").values_list("pk", flat=True))
            executions = list(daily_executions(user, cycle, day))
            if (
                not executions
                or fingerprint != day_fingerprint(executions)
                or set(entries) != {e.pk for e in executions}
            ):
                raise ValidationError("当天任务或填报已变化，请重新打开页面后填写。")
            if not problems.strip() and any(
                set(entries[row.pk]) != {item["id"] for item in checklist_items(row.training_task)}
                for row in executions
            ):
                raise ValidationError("有未完成项目时，请说明未完成的部分或存在的问题。")
            # Keep daily notes and photos in the existing private progress storage once.
            shared_execution_id = min(execution.pk for execution in executions)
            for execution in executions:
                items = checklist_items(execution.training_task)
                selected = set(entries[execution.pk])
                if not selected.issubset({item["id"] for item in items}):
                    raise ValidationError("勾选项已变化，请重新填写。")
                checklist = [{**item, "done": item["id"] in selected} for item in items]
                process.save_progress(
                    execution,
                    user,
                    training_date=day,
                    completed="",
                    problems=problems if execution.pk == shared_execution_id else "",
                    files=images if execution.pk == shared_execution_id else (),
                    checklist=checklist,
                    written_files=written_files,
                )
                status = (
                    TaskExecution.Status.COMPLETED
                    if len(selected) == len(items)
                    else TaskExecution.Status.PARTIALLY_COMPLETED
                    if selected
                    else TaskExecution.Status.ASSIGNED
                )
                now = timezone.now()
                updates = {"status": status, "updated_at": now}
                if selected and execution.started_at is None:
                    updates["started_at"] = now
                if status == TaskExecution.Status.COMPLETED and execution.completed_at is None:
                    updates["completed_at"] = now
                TaskExecution.objects.filter(pk=execution.pk).update(**updates)
                if execution.status != status:
                    TrainingStateChange.objects.create(
                        execution=execution, actor=user, before=execution.status, after=status
                    )
    except Exception:
        for storage, name in written_files:
            storage.delete(name)
        raise


def training_day_url(view, cycle, day):
    query = {"cycle": cycle, "training_date": day.isoformat()}
    if view == "training:log_ai_start" and day < timezone.localdate():
        query["history"] = 1
    return f"{reverse(view)}?{urlencode(query)}"


def training_upload_url(cycle, day):
    view = "training:log_backfill" if day < timezone.localdate() else "training:log_create"
    return training_day_url(view, cycle, day)


def training_day_is_available(member, day, today):
    if not member or day > today:
        return False
    cycle = member.training_cycle
    if day < cycle.start_date or (cycle.end_date and day > cycle.end_date):
        return False
    if day == today:
        return member.is_current and cycle.status == cycle.Status.ACTIVE
    return cycle.status in (cycle.Status.ACTIVE, cycle.Status.COMPLETED)
