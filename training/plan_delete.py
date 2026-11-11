"""误建训练计划的删除预览与确认。"""

import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError

from .models import TaskExecution, TrainingChangeRecord, TrainingPlan, TrainingTask
from .scheduling import privileged


# 仅允许随草稿删除的日常保存记录。未知动作及发布、审批等历史默认受保护。
DRAFT_ACTIONS = (
    "保存计划及职责", "维护负责教练", "维护值班人员", "调整值班顺序",
    "添加计划成员", "退出计划成员", "首次填写排班", "保存排班", "快捷交换排班",
    "保存任务", "添加任务附件", "修正技能关联", "批量追加任务", "导入排班和任务草稿",
)


def blocked_reason(plan):
    if plan.status != TrainingPlan.Status.DRAFT or plan.published_at or plan.schedule_published_at:
        return "仅可删除从未发布的草稿计划。"
    if (
        plan.personal_tasks.exists()
        or TaskExecution.objects.filter(training_task__training_plan=plan).exists()
    ):
        return "计划已有任务分配、执行记录或自主任务，不能删除。"
    if plan.schedule_changes.exists():
        return "计划已有调整审批记录，不能删除。"
    if plan.tasks.exclude(status=TrainingTask.Status.DRAFT).exists():
        return "计划已有非草稿任务，不能删除。"
    if plan.change_records.exclude(action__in=DRAFT_ACTIONS).exists():
        return "计划已有发布或其他受保护的历史记录，不能删除。"
    return ""


def preview(plan, user):
    if not privileged(user):
        raise PermissionDenied
    if reason := blocked_reason(plan):
        raise ValidationError(reason)

    people = set(plan.participants.values_list("user_id", flat=True))
    people.update(plan.staff_members.values_list("user_id", flat=True))
    for roster in (plan.responsible_coaches, plan.duty_personnel, plan.schedulers, plan.approvers, plan.task_managers):
        people.update(roster.values_list("pk", flat=True))
    days = plan.schedule_days.count()
    tasks = list(plan.tasks.order_by("pk").values_list("pk", "updated_at"))
    # 正常业务写入持有计划锁，并刷新计划更新时间和追加变更记录。
    revision = plan.change_records.order_by("-pk").values_list("pk", flat=True).first()
    state = [plan.updated_at, revision, sorted(people), days, tasks]
    digest = hashlib.sha256(json.dumps(state, default=str).encode()).hexdigest()
    return {"people": len(people), "days": days, "tasks": len(tasks), "digest": digest}


@transaction.atomic
def execute(plan, user, digest):
    current = TrainingPlan.objects.select_for_update().filter(pk=plan.pk).first()
    if current is None:
        raise ValidationError("训练计划已删除。")
    if preview(current, user)["digest"] != digest:
        raise ValidationError("训练计划内容已变化，请重新预览。")
    try:
        # 普通入口仍禁止删除变更记录。此处只移除通过复核的草稿保存记录。
        TrainingChangeRecord._base_manager.filter(training_plan=current, action__in=DRAFT_ACTIONS).delete()
        current.tasks.filter(status=TrainingTask.Status.DRAFT).delete()
        current.participants.all().delete()
        current.staff_members.all().delete()
        current.delete()
    except ProtectedError as exc:
        raise ValidationError("计划存在受保护的关联记录，不能删除。") from exc
