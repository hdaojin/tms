from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    TaskExecution, TrainingCycle, TrainingCycleMember, TrainingCycleSkillTreeVersion, TrainingLog,
    TrainingScheduleSlot, TrainingTask, TrainingTaskDomain,
)
from .log_files import DUPLICATE_LOG_MESSAGE, build_log_filename
from core.uploads import TRAINING_LOG_UPLOAD_SPEC


def validate_cycle_tree_versions(cycle, selected):
    """校验快照调整及被排班、任务和阶段周期使用的领域。"""
    existing = dict(cycle.skill_tree_version_links.values_list("technical_domain_id", "skill_tree_version_id"))
    if cycle.skill_tree_bindings_locked:
        if not cycle.can_add_skill_tree_bindings:
            raise ValidationError("训练周期的技能树版本快照已经锁定，不能再修改。")
        if any(domain_id not in selected or selected[domain_id].pk != tree_id for domain_id, tree_id in existing.items()):
            raise ValidationError("进行中的周期只能追加新领域，已有快照不能替换或删除。")
    removed = set(existing) - set(selected)
    if TrainingScheduleSlot.objects.filter(day__training_plan__training_cycle=cycle).filter(
        Q(domains__pk__in=removed) | Q(primary_domain_id__in=removed)
    ).exists():
        raise ValidationError("该技术领域已被排班使用，不能从周期中移除。")
    used_domain = TrainingTaskDomain.objects.filter(
        training_task__training_plan__training_cycle=cycle, technical_domain_id__in=removed
    ).select_related("technical_domain").first()
    if used_domain:
        raise ValidationError(f"技术领域“{used_domain.technical_domain.name}”已被训练任务使用，不能从周期中移除。")
    child_link = TrainingCycleSkillTreeVersion.objects.filter(
        training_cycle__parent=cycle, technical_domain_id__in=removed
    ).select_related("technical_domain").first()
    if child_link:
        raise ValidationError(f"技术领域“{child_link.technical_domain.name}”已被阶段周期使用，不能从父周期中移除。")
    for domain_id, tree in selected.items():
        if tree.technical_domain_id != domain_id or tree.technical_domain.skill_project_id != cycle.skill_project_id:
            raise ValidationError("所选技能树版本不属于周期的技能项目和对应技术领域。")
    if cycle.parent_id:
        allowed = set(cycle.parent.skill_tree_version_links.values_list("technical_domain_id", flat=True))
        if not set(selected).issubset(allowed):
            raise ValidationError("阶段周期只能使用父周期已经包含的技术领域。")


@transaction.atomic
def save_cycle_tree_versions(cycle, selected):
    """重新锁定周期并校验后，原子保存领域版本快照。"""
    cycle = TrainingCycle.objects.select_for_update().get(pk=cycle.pk)
    validate_cycle_tree_versions(cycle, selected)
    existing_domains = set(cycle.skill_tree_version_links.values_list("technical_domain_id", flat=True))
    locked = cycle.skill_tree_bindings_locked
    for domain_id, tree in selected.items():
        if locked and domain_id in existing_domains:
            continue
        TrainingCycleSkillTreeVersion.objects.update_or_create(
            training_cycle=cycle, technical_domain_id=domain_id, defaults={"skill_tree_version": tree}
        )
    for link in cycle.skill_tree_version_links.exclude(technical_domain_id__in=selected):
        link.delete()
    cycle.save(update_fields=["updated_at"])
    return cycle


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
        if log.training_date >= timezone.localdate():
            raise ValidationError({"training_date": "补交历史训练日志的日期必须早于今天。"})
    elif not member.is_current or cycle.status != cycle.Status.ACTIVE:
        raise ValidationError("未设置有效的当前周期，请联系管理员。")
    elif log.training_date != timezone.localdate():
        raise ValidationError({"training_date": "日常新增训练日志的训练日期必须为今天。"})
    if log.training_date < cycle.start_date or (cycle.end_date and log.training_date > cycle.end_date):
        raise ValidationError("训练日期必须位于训练周期日期范围内。")


def save_training_log(log, executions, *, backfill=False):
    """先预留数据库唯一键，再保存文件；失败时清理本次新增文件。"""
    if not log.pk and not log.document:
        raise ValidationError({"document": "请上传日志文件。"})
    upload = log.document if log.document and not log.document._committed else None
    if upload:
        TRAINING_LOG_UPLOAD_SPEC.validate_file(upload)
    saved_name = None
    storage = log.document.storage
    try:
        with transaction.atomic():
            log.clean()
            if not log.pk:
                get_user_model().objects.select_for_update().get(pk=log.author_id)
                validate_new_log(log, backfill=backfill)
                log.is_backfill = backfill
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
    if task.schedule_slot_id:
        from .scheduling import publish_slot_task
        if user is None:
            raise ValidationError("发布计划内任务必须提供操作者。")
        return publish_slot_task(task, user)
    if not task.domain_links.exists():
        raise ValidationError("发布训练任务前必须至少关联一个技术领域。")
    cycle_domain_ids = set(
        task.training_plan.training_cycle.skill_tree_version_links.values_list("technical_domain_id", flat=True)
    )
    task_domain_ids = set(task.domain_links.values_list("technical_domain_id", flat=True))
    if not task_domain_ids.issubset(cycle_domain_ids):
        raise ValidationError("训练任务只能使用周期已固定技能树版本的技术领域。")
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
    from .models import TrainingPlan
    plan_id = execution.training_task.training_plan_id
    TrainingPlan.objects.select_for_update().get(pk=plan_id)
    execution = TaskExecution.objects.select_for_update().get(pk=execution.pk)
    if execution.user_id != user.pk:
        raise ValidationError("选手只能修改自己的任务执行记录。")
    if execution.training_task.schedule_slot_id and (
        execution.training_task.status != "published" or execution.status == "cancelled" or execution.revoked_at
    ):
        raise ValidationError("任务未发布或任务、分配已取消，不能更新执行。")
    allowed = {"status", "actual_minutes", "completion_note", "problems", "problem_resolved", "solution", "reflection"}
    if execution.training_task.schedule_slot_id and "status" in values:
        from .process import change_state
        execution = change_state(execution, user, values.pop("status"))
    for key, value in values.items():
        if key in allowed:
            setattr(execution, key, value)
    execution.save()
    return execution


@transaction.atomic
def record_coach_feedback(execution, *, user, feedback):
    execution = TaskExecution.objects.select_for_update().get(pk=execution.pk)
    task = execution.training_task
    if task.schedule_slot_id:
        from .process import add_feedback
        return add_feedback(execution, user, feedback)
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
