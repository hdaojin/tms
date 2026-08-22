from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import TaskExecution, TrainingCycleMember, TrainingTask


@transaction.atomic
def publish_training_task(task, competitor_ids, user=None):
    task = TrainingTask.objects.select_for_update().get(pk=task.pk)
    if not task.domain_links.exists():
        raise ValidationError("发布训练任务前必须至少关联一个技术领域。")
    cycle_domain_ids = set(
        task.training_plan.training_cycle.skill_tree_version_links.values_list("technical_domain_id", flat=True)
    )
    task_domain_ids = set(task.domain_links.values_list("technical_domain_id", flat=True))
    if not task_domain_ids.issubset(cycle_domain_ids):
        raise ValidationError("训练任务只能使用周期已固定技能树版本的技术领域。")
    if not task.skill_links.filter(role="primary").exists():
        raise ValidationError("发布训练任务前必须至少关联一个主要技能。")
    if not task.coach_links.exists():
        raise ValidationError("发布训练任务前必须至少分配一位教练。")
    competitor_ids = set(competitor_ids)
    valid_ids = set(
        task.training_plan.training_cycle.members.filter(
            role=TrainingCycleMember.Role.COMPETITOR, user_id__in=competitor_ids
        ).values_list("user_id", flat=True)
    )
    if valid_ids != competitor_ids:
        raise ValidationError("只能把训练任务分配给当前周期的选手。")
    task.status = TrainingTask.Status.PUBLISHED
    task.save(update_fields=["status", "updated_at"])
    for competitor_id in valid_ids:
        TaskExecution.objects.get_or_create(training_task=task, user_id=competitor_id)
    return task


@transaction.atomic
def update_execution_facts(execution, *, user, **values):
    execution = TaskExecution.objects.select_for_update().get(pk=execution.pk)
    if execution.user_id != user.pk:
        raise ValidationError("选手只能修改自己的任务执行记录。")
    allowed = {"status", "actual_minutes", "completion_note", "problems", "problem_resolved", "solution", "reflection"}
    for key, value in values.items():
        if key in allowed:
            setattr(execution, key, value)
    execution.save()
    return execution


@transaction.atomic
def record_coach_feedback(execution, *, user, feedback):
    execution = TaskExecution.objects.select_for_update().get(pk=execution.pk)
    task = execution.training_task
    from standards.selectors import is_project_admin

    if not is_project_admin(user) and not task.coach_links.filter(user=user).exists():
        raise ValidationError("只有任务教练或项目管理员可以填写教练反馈。")
    execution.coach_feedback = feedback
    execution.feedback_by = user
    execution.feedback_at = timezone.now()
    execution.save(update_fields=["coach_feedback", "feedback_by", "feedback_at", "updated_at"])
    return execution


def suggest_executions_for_log(user, cycle, date):
    return (
        TaskExecution.objects.filter(user=user, training_task__training_plan__training_cycle=cycle)
        .filter(training_task__planned_date=date)
        .select_related("training_task")
    )


def build_log_summary_context(user, cycle, date):
    executions = list(suggest_executions_for_log(user, cycle, date))
    return {"date": date, "cycle": cycle, "executions": executions}


def build_training_log_archive(queryset):
    buffer = BytesIO()
    used_names = set()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for log in queryset.select_related("training_cycle", "author"):
            if not log.document:
                continue
            user_label = getattr(log.author, "display_name", None) or log.author.get_username()
            filename = PurePosixPath(log.document.name).name
            arcname = PurePosixPath(
                f"{log.training_date:%Y-%m}",
                log.training_cycle.code,
                user_label,
                f"{log.training_date:%Y%m%d}-{filename}",
            )
            unique_name = str(arcname)
            suffix = 1
            while unique_name in used_names:
                unique_name = str(arcname.with_name(f"{arcname.stem}-{suffix}{arcname.suffix}"))
                suffix += 1
            used_names.add(unique_name)
            with log.document.open("rb") as source:
                archive.writestr(unique_name, source.read())
    buffer.seek(0)
    return buffer.getvalue()
