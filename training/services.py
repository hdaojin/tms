from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import TaskExecution, TrainingCycle, TrainingCycleMember, TrainingLog, TrainingTask
from .log_files import DUPLICATE_LOG_MESSAGE, build_log_filename


@transaction.atomic
def save_cycle_member(member):
    """以用户行锁串行化当前周期切换，失败时恢复原设置。"""
    get_user_model().objects.select_for_update().get(pk=member.user_id)
    member.training_cycle = TrainingCycle.objects.get(pk=member.training_cycle_id)
    member.clean()
    if member.is_current:
        TrainingCycleMember.objects.filter(user_id=member.user_id, is_current=True).exclude(pk=member.pk).update(
            is_current=False
        )
    member.full_clean()
    member.save()
    return member


@transaction.atomic
def remove_cycle_member(member):
    get_user_model().objects.select_for_update().get(pk=member.user_id)
    member.delete()


def validate_new_log(log, *, backfill=False):
    cycle = TrainingCycle.objects.get(pk=log.training_cycle_id)
    member = cycle.members.filter(user_id=log.author_id).first()
    if not member:
        raise ValidationError("请先加入所选训练周期，再提交日志。")
    if backfill:
        if cycle.status not in {cycle.Status.ACTIVE, cycle.Status.COMPLETED}:
            raise ValidationError("历史补交仅支持进行中或已完成的训练周期。")
    elif not member.is_current or cycle.status != cycle.Status.ACTIVE:
        raise ValidationError("未设置有效的当前周期，请联系管理员。")
    if log.training_date < cycle.start_date or (cycle.end_date and log.training_date > cycle.end_date):
        raise ValidationError("训练日期必须位于训练周期日期范围内。")


def save_training_log(log, executions, *, backfill=False):
    """先预留数据库唯一键，再保存文件；失败时清理本次新增文件。"""
    upload = log.document if log.document and not log.document._committed else None
    saved_name = None
    storage = log.document.storage
    try:
        with transaction.atomic():
            if not log.pk:
                get_user_model().objects.select_for_update().get(pk=log.author_id)
                validate_new_log(log, backfill=backfill)
            if log.pk:
                previous = TrainingLog.objects.select_for_update().get(pk=log.pk)
                if previous.training_cycle_id != log.training_cycle_id:
                    raise ValidationError("已有日志不可修改训练周期。")
                if previous.document and (
                    upload or previous.document.name != log.document.name
                    or previous.training_cycle_id != log.training_cycle_id
                    or previous.training_date != log.training_date
                ):
                    raise ValidationError("已有日志文件，如需修改请先删除日志后重新上传。")
            if upload:
                log.canonical_filename = build_log_filename(log, upload.name)
                log.document = None
            log.save()
            if upload:
                log.document.save(log.canonical_filename, upload, save=False)
                saved_name = log.document.name
                log.save(update_fields=["document", "updated_at"])
            log.executions.set(executions)
    except Exception as exc:
        if saved_name:
            storage.delete(saved_name)
        if isinstance(exc, IntegrityError):
            raise ValidationError(DUPLICATE_LOG_MESSAGE) from exc
        raise


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
    if not user.is_superuser and not task.coach_links.filter(user=user).exists():
        raise ValidationError("只有任务教练或超级管理员可以填写教练反馈。")
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
