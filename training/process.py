"""训练执行事实、进度和指导反馈；不修改官方任务定义。"""

from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from .models import (
    PersonalTrainingTask,
    TaskExecution,
    TrainingAssignmentCoach,
    TrainingCoachFeedback,
    TrainingProgress,
    TrainingProgressAttachment,
    TrainingProgressRevision,
    TrainingStateChange,
)
from .scheduling import privileged

STATES = [("assigned", "未开始"), ("in_progress", "进行中"), ("completed", "已完成"), ("unfinished", "未完成")]


def personal_tasks_for(user):
    tasks = PersonalTrainingTask.objects.filter(deleted_at__isnull=True)
    if not user.has_perm("training.view_personaltrainingtask"):
        return tasks.none()
    if privileged(user):
        return tasks
    history = TrainingAssignmentCoach.objects.filter(
        user=user,
        execution__user_id=OuterRef("user_id"),
        execution__training_task__training_plan_id=OuterRef("training_plan_id"),
    )
    return tasks.annotate(_responsible=Exists(history)).filter(Q(user=user) | Q(_responsible=True))


def is_coach(user, target):
    if privileged(user):
        return True
    if isinstance(target, TaskExecution):
        task = target.training_task
        if task.schedule_slot_id:
            return task.schedule_slot.coaches.filter(pk=user.pk).exists()
        return task.coach_links.filter(user=user).exists()
    return TrainingAssignmentCoach.objects.filter(
        user=user,
        execution__user_id=target.user_id,
        execution__training_task__training_plan_id=target.training_plan_id,
    ).exists()


def visible_target(user, target):
    permission = (
        "training.view_taskexecution" if isinstance(target, TaskExecution) else "training.view_personaltrainingtask"
    )
    if not user.has_perm(permission):
        return False
    if isinstance(target, PersonalTrainingTask) and target.deleted_at:
        return privileged(user)
    if isinstance(target, TaskExecution) and target.training_task.schedule_slot_id and target.user_id == user.pk:
        if target.status == "cancelled" or target.revoked_at or target.training_task.status != "published" or not target.training_task.training_plan.published_at or not target.training_task.training_plan.schedule_published_at:
            return False
    return privileged(user) or target.user_id == user.pk or is_coach(user, target)


def target_fields(target):
    return {"execution": target} if isinstance(target, TaskExecution) else {"personal_task": target}


def lock_target(target):
    return type(target).objects.select_for_update().get(pk=target.pk)


def require_owner(user, target, permission):
    if not user.has_perm(permission) or not visible_target(user, target) or target.user_id != user.pk:
        raise PermissionDenied


@transaction.atomic
def change_state(target, user, status):
    target = lock_target(target)
    require_owner(
        user,
        target,
        "training.change_taskexecution"
        if isinstance(target, TaskExecution)
        else "training.change_personaltrainingtask",
    )
    if status not in dict(STATES):
        raise ValidationError("请选择未开始、进行中、已完成或未完成。")
    previous = target.status
    target.status = status
    target.full_clean()
    target.save()
    if previous != status:
        TrainingStateChange.objects.create(**target_fields(target), actor=user, before=previous, after=status)
    return target


@transaction.atomic
def save_progress(target, user, *, completed, problems, progress=None, files=(), training_date=None,
                  checklist=None, written_files=None, issues=None):
    target = lock_target(target)
    if training_date is not None:
        from .daily_progress import validate_daily_execution

        validate_daily_execution(target, user, training_date)
        progress = target.progress_records.filter(training_date=training_date).first()
    require_owner(
        user, target, "training.add_trainingprogress" if progress is None else "training.change_trainingprogress"
    )
    if progress:
        progress = TrainingProgress.objects.select_for_update().get(pk=progress.pk, **target_fields(target))
        if progress.author_id != user.pk:
            raise PermissionDenied
        if progress.checklist is not None and checklist is None:
            raise ValidationError("请通过训练完成情况页面修订。")
        TrainingProgressRevision.objects.create(
            progress=progress, actor=user, completed=progress.completed, problems=progress.problems,
            checklist=progress.checklist, issues=progress.issues,
        )
    else:
        progress = TrainingProgress(**target_fields(target), author=user, training_date=training_date)
    if checklist is None and not (completed.strip() or problems.strip() or files):
        raise ValidationError("请填写完成内容、存在问题或上传附件。")
    progress.completed, progress.problems = completed, problems
    progress.checklist = checklist
    if issues is not None:
        progress.issues = issues
    progress.full_clean()
    progress.save()
    attachments = [
        TrainingProgressAttachment(
            progress=progress, file=file, uploaded_by=user, original_filename=Path(file.name).name
        )
        for file in files
    ]
    for attachment in attachments:
        attachment.full_clean()
    stored = []
    try:
        for attachment in attachments:
            attachment.save()
            stored.append((attachment.file.storage, attachment.file.name))
    except Exception:
        for storage, name in stored:
            storage.delete(name)
        raise
    if written_files is not None:
        written_files.extend(stored)
    return progress


@transaction.atomic
def add_feedback(target, user, content):
    target = lock_target(target)
    if (
        not user.has_perm("training.add_trainingcoachfeedback")
        or not visible_target(user, target)
        or not is_coach(user, target)
    ):
        raise PermissionDenied
    if not content.strip():
        raise ValidationError("请填写指导反馈。")
    feedback = TrainingCoachFeedback(**target_fields(target), author=user, content=content)
    feedback.full_clean()
    feedback.save()
    return feedback


@transaction.atomic
def save_personal_task(plan, user, values, *, task=None):
    permission = "training.change_personaltrainingtask" if task else "training.add_personaltrainingtask"
    if not user.has_perm(permission):
        raise PermissionDenied
    if task:
        task = PersonalTrainingTask.objects.select_for_update().get(pk=task.pk, training_plan=plan)
        if not privileged(user) and task.user_id != user.pk:
            raise PermissionDenied
        if task.deleted_at:
            raise ValidationError("已删除任务不能修改。")
    else:
        if not plan.participants.filter(user=user, is_active=True).exists():
            raise PermissionDenied
        task = PersonalTrainingTask(training_plan=plan, user=user)
    for field in ("date", "period", "domain", "title", "description"):
        if field in values:
            setattr(task, field, values[field])
    task.full_clean()
    task.save()
    if "skills" in values:
        skills = list(values["skills"])
        if any(skill.skill_project_id != plan.training_cycle.skill_project_id for skill in skills):
            raise ValidationError("技能必须属于计划的技能项目。")
        task.skills.set(skills)
    return task


@transaction.atomic
def delete_personal_task(task, user):
    task = lock_target(task)
    if not user.has_perm("training.delete_personaltrainingtask") or not (privileged(user) or task.user_id == user.pk):
        raise PermissionDenied
    task.deleted_at, task.deleted_by = timezone.now(), user
    task.save(update_fields=["deleted_at", "deleted_by", "updated_at"])


def official_completion(plan, user=None):
    assignments = TaskExecution.objects.filter(
        training_task__training_plan=plan,
        training_task__status="published",
        training_task__schedule_slot__ends_at__lte=timezone.now(),
        revoked_at__isnull=True,
    ).exclude(status="cancelled")
    if user is not None:
        assignments = assignments.filter(user=user, training_task__training_plan__published_at__isnull=False, training_task__training_plan__schedule_published_at__isnull=False)
    counts = assignments.aggregate(total=Count("pk"), completed=Count("pk", filter=Q(status="completed")))
    counts["rate"] = counts["completed"] / counts["total"] if counts["total"] else None
    return counts
