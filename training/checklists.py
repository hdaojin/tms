from uuid import uuid4

from django.core.exceptions import ValidationError

from .models import TrainingProgress


def outline_items(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def checklist_items(task):
    return task.subtasks or [{"id": "task", "title": task.title}]


def validate_subtask_change(task, titles):
    previous = [item["title"] for item in task.subtasks]
    if titles == previous:
        return False
    if (
        task.pk
        and TrainingProgress.objects.filter(
            execution__training_task=task,
            checklist__isnull=False,
        ).exists()
    ):
        raise ValidationError("已有选手填报，子任务清单不能再修改。")
    if any(not isinstance(title, str) or not title.strip() for title in titles):
        raise ValidationError("请输入有效的子任务内容。")
    return True


def update_subtasks(task, titles):
    if not validate_subtask_change(task, titles):
        return
    existing = {}
    for item in reversed(task.subtasks):
        existing.setdefault(item["title"], []).append(item["id"])
    task.subtasks = [
        {"id": existing[title].pop() if existing.get(title) else uuid4().hex, "title": title} for title in titles
    ]


def completion_counts(record):
    if record is None or record.checklist is None:
        return None
    return sum(item["done"] for item in record.checklist), len(record.checklist)
