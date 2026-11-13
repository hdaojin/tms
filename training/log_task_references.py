import hashlib
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError

from .log_references import REFERENCE_SPEC, TEXT_EXTENSIONS, read_reference
from .models import TrainingTaskAttachment
from .selectors import visible_training_tasks_for

MAX_TASK_REFERENCE_TEXT = 12000


def task_references(user, tasks):
    if not user.has_perm("training.view_trainingtaskattachment"):
        return {}
    visible = visible_training_tasks_for(user).filter(pk__in=[task.pk for task in tasks])
    attachments = TrainingTaskAttachment.objects.filter(training_task__in=visible).order_by("pk")
    results, remaining = {}, MAX_TASK_REFERENCE_TEXT
    limit = REFERENCE_SPEC.max_size_mb * 1024 * 1024
    for attachment in attachments:
        if remaining <= 0:
            break
        name = attachment.original_filename or attachment.file.name
        if not name or Path(name).suffix.lower().lstrip(".") not in ("pdf", "docx", *TEXT_EXTENSIONS):
            continue
        try:
            if attachment.file.size > limit:
                continue
            with attachment.file.open("rb") as file:
                content = file.read(limit + 1)
            if len(content) > limit:
                continue
            reference = BytesIO(content)
            reference.name = name
            reference.size = len(content)
            excerpt = read_reference(reference)
        except (OSError, ValueError, ValidationError):
            continue
        excerpt = excerpt[:remaining]
        remaining -= len(excerpt)
        results.setdefault(attachment.training_task_id, []).append(
            (attachment.pk, hashlib.sha256(content).hexdigest(), name, excerpt)
        )
    return results
