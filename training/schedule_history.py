"""将审计快照转换为可读中文；不把机器字段和账号主键作为主要展示。"""

import json

from django.contrib.auth import get_user_model
from accounts.services.users import get_user_display_name
from standards.models import TechnicalDomain, Skill

LABELS = {
    "date": "日期",
    "day_id": "日期记录",
    "slots": "交换时段",
    "tasks": "随排班交换的任务",
    "slot": "时段记录",
    "updated_at": "最后保存时间",
    "publish": "发布任务",
    "include_past": "同时纠正历史时间",
    "times": "计划作息",
    **{f"{period}_{edge}": f"{label}{edge_label}时间" for period, label in [("early", "早读"), ("morning", "上午"), ("afternoon", "下午"), ("evening", "晚上")] for edge, edge_label in [("start", "开始"), ("end", "结束")]},
    "duty_all": "全体值班",
    "duty_coaches": "值班人员",
    "note": "日备注",
    "period": "时段",
    "kind": "类型",
    "domains": "技术领域",
    "primary_domain": "主要领域",
    "coaches_all": "全体负责",
    "coaches": "负责教练",
    "primary_coach": "主要教练",
    "title": "任务标题",
    "description": "描述",
    "requirements": "要求",
    "estimated_minutes": "预计分钟",
    "priority": "优先级",
    "order": "顺序",
    "status": "状态",
    "assign_all": "全体选手",
    "skills": "技能",
    "selected_competitors": "指定选手",
    "user_id": "人员",
    "type": "条目类型",
    "id": "条目",
    "revision": "版本",
    "revoked_at": "撤销时间",
    "revoke_reason": "撤销原因",
    "before": "调整前",
    "after": "调整后",
}
VALUES = {
    "early": "早读",
    "morning": "上午",
    "afternoon": "下午",
    "evening": "晚上",
    "technical": "技术训练",
    "general": "其他",
    "comprehensive": "综合",
    "rest": "休息",
    "unused": "不安排",
    "pending": "待处理",
    "draft": "草稿",
    "published": "已发布",
    "cancelled": "已取消",
    "assigned": "已分配",
    "in_progress": "进行中",
    "completed": "已完成",
    "archived": "已归档",
    "partially_completed": "部分完成",
    "blocked": "受阻",
    "normal": "普通",
    "high": "高",
    "low": "低",
    "urgent": "紧急",
    "day": "每日安排",
    "slot": "排班时段",
    "swap": "交换排班",
    "times": "修改计划作息",
    "task": "修改训练任务",
}


def decorate_history(records=(), changes=()):
    records, changes = list(records), list(changes)
    user_ids, domain_ids, skill_ids = set(), set(), set()

    def collect(value, key=""):
        if isinstance(value, dict):
            for name, item in value.items():
                collect(item, name)
        elif isinstance(value, list):
            for item in value:
                collect(item, key)
        elif isinstance(value, int) and not isinstance(value, bool):
            if key in {
                "duty_coaches",
                "coaches",
                "primary_coach",
                "selected_competitors",
                "user_id",
                "排班人员",
                "审批人员",
                "任务管理员",
            }:
                user_ids.add(value)
            elif key in {"domains", "primary_domain"}:
                domain_ids.add(value)
            elif key == "skills":
                skill_ids.add(value)

    for record in records:
        collect(record.before)
        collect(record.after)
    for change in changes:
        collect(change.payload)
    users = {user.pk: get_user_display_name(user) for user in get_user_model().objects.filter(pk__in=user_ids)}
    domains = dict(TechnicalDomain.objects.filter(pk__in=domain_ids).values_list("pk", "name"))
    skills = dict(Skill.objects.filter(pk__in=skill_ids).values_list("pk", "name"))

    def readable(value, key=""):
        if isinstance(value, dict):
            return {LABELS.get(name, name): readable(item, name) for name, item in value.items() if name != "entry_guard"}
        if isinstance(value, list):
            return [readable(item, key) for item in value]
        if isinstance(value, bool):
            return "是" if value else "否"
        if value is None:
            return "未设置"
        if key in {
            "duty_coaches",
            "coaches",
            "primary_coach",
            "selected_competitors",
            "user_id",
            "排班人员",
            "审批人员",
            "任务管理员",
        }:
            return users.get(value, str(value))
        if key in {"domains", "primary_domain"}:
            return domains.get(value, str(value))
        if key == "skills":
            return skills.get(value, str(value))
        return VALUES.get(value, value) if isinstance(value, str) else value

    for record in records:
        record.display_diff = json.dumps(
            {"修改前": readable(record.before), "修改后": readable(record.after)}, ensure_ascii=False, indent=2
        )
    for change in changes:
        change.display_payload = json.dumps(readable(change.payload), ensure_ascii=False, indent=2)
    return records, changes
