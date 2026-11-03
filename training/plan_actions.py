"""训练计划详情中的快捷操作及可用状态。"""

from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.urls import reverse

from . import entry_operations, plan_clear, plan_workbooks, scheduling


def _reason(check, *args, **kwargs):
    try:
        check(*args, **kwargs)
    except ValidationError as exc:
        return "；".join(exc.messages)
    return ""


def _schedule_reason(plan):
    if not plan.published_at:
        return "请先发布训练计划。"
    if plan.schedule_published_at:
        return "排班已发布。"
    reason = _reason(scheduling.require_rosters, plan)
    if reason:
        return reason
    days = list(plan.schedule_days.prefetch_related("duty_coaches", "slots__coaches"))
    if len(days) != (plan.end_date - plan.start_date).days + 1:
        return "日期框架不完整。"
    for day in days:
        slots = list(day.slots.all())
        enabled = [slot for slot in slots if slot.is_configured]
        if len(slots) != 4 or any(not scheduling.slot_complete(slot, has_plan_coaches=True) for slot in enabled):
            return f"{day.date} 的排班尚未填完整。"
        duty_optional = enabled and all(slot.kind in {"rest", "unused"} for slot in enabled)
        if not duty_optional and not (day.duty_all or list(day.duty_coaches.all())):
            return f"{day.date} 尚未安排值班人员。"
    return ""


def plan_actions(plan, user, return_query):
    actions = []

    def action(label, route=None, *args, reason="", description="", post=False):
        url = reverse(f"training:{route}", args=[plan.pk, *args]) if route else ""
        if route == "withdraw_publication" and return_query:
            url += "?" + urlencode({"return_query": return_query})
        return {"label": label, "url": url, "reason": reason, "post": post, "tooltip": reason or description}

    scheduler = scheduling.can_schedule(user, plan)
    can_add_tasks = user.has_perm("training.add_trainingtask")
    can_change_tasks = user.has_perm("training.change_trainingtask")
    unavailable = "暂未开放"
    if scheduler and can_add_tasks:
        reason = _reason(plan_workbooks.check_empty_plan, plan, user) or _reason(scheduling.require_rosters, plan)
        actions.append(action("导入 Excel", "plan_import", reason=reason, description="预览并导入排班和任务草稿。"))
    actions.extend([
        action(label, reason=unavailable)
        for label in ("快速 / 批量排班", "快捷调班", "复制排班") if scheduler
    ])
    if scheduler and can_add_tasks:
        actions.append(action("批量填写任务", reason=unavailable))
    if user.has_perm("training.add_personaltrainingtask") and plan.participants.filter(user=user, is_active=True).exists():
        actions.append(action("添加自主任务", "personal_create", description="为自己添加自主训练任务。"))
    if scheduler:
        actions.append(action("统一发布排班", "schedule_publish", reason=_schedule_reason(plan), post=True, description="发布整份计划的排班。"))
        if can_change_tasks:
            reason = ""
            if not (plan.published_at and plan.schedule_published_at):
                reason = "请先发布训练计划和整份排班。"
            elif not plan.tasks.filter(status="draft").exists():
                reason = "没有待发布的任务草稿。"
            actions.append(action("统一发布全部任务", "publish_all_tasks", reason=reason, description="预览并发布全部任务草稿。"))
    if user.has_perm("training.view_trainingtask"):
        actions.append(action("导出 Excel", "plan_export", description="下载已发布的训练计划 Excel。", reason="" if plan.schedule_published_at else "排班发布后才能导出。"))
    if scheduling.privileged(user):
        actions.extend([
            action("撤回全部任务发布", "plan_clear", "withdraw_tasks", description="预览并撤回全部已发布任务。",
                   reason=_reason(plan_clear.state, plan, user, "withdraw_tasks", preview=False)),
            *[action(label, "withdraw_publication", level, description=f"预览并确认{label}。",
                     reason=_reason(entry_operations.withdrawal_state, plan, user, level, preview=False))
              for label, level in (("撤回排班发布", "schedule"),)],
        ])
    if scheduler:
        actions.extend([
            action(label, "plan_clear", key, description=f"预览并确认{label}。", reason=_reason(plan_clear.state, plan, user, key, preview=False))
            for label, key in (("清空全部任务", "clear_tasks"), ("清空全部排班", "clear_schedule"))
            if key != "clear_tasks" or can_change_tasks
        ])
    return actions
