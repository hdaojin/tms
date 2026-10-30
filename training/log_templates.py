"""日志模板的下载范围、写入及文件清理。"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import TrainingCycle, TrainingLogTemplate


def template_submission_cycles(user, *, backfill=False):
    if not user.is_active or not user.has_perm("training.add_traininglog"):
        return TrainingCycle.objects.none()
    cycles = TrainingCycle.objects.filter(members__user=user)
    if backfill:
        return cycles.filter(status__in=[TrainingCycle.Status.ACTIVE, TrainingCycle.Status.COMPLETED])
    return TrainingCycle.objects.filter(members__user=user, members__is_current=True, status=TrainingCycle.Status.ACTIVE)


def downloadable_log_templates(user, *, backfill=False):
    return TrainingLogTemplate.objects.filter(
        is_active=True, training_cycle__in=template_submission_cycles(user, backfill=backfill),
    )


def require_template_permission(user, action):
    if not user.is_active or not user.has_perms([
        "training.view_traininglogtemplate", f"training.{action}_traininglogtemplate",
    ]):
        raise PermissionDenied


def delete_template_file(sender, instance, using=None, **kwargs):
    if instance.file:
        storage, name = instance.file.storage, instance.file.name
        transaction.on_commit(lambda: storage.delete(name), using=using, robust=True)


def save_log_template(template, *, actor):
    require_template_permission(actor, "change" if template.pk else "add")
    if not template.file:
        raise ValidationError({"file": "请上传模板文件。"})
    upload = template.file if template.file and not template.file._committed else None
    storage = template.file.storage
    old_name = None
    try:
        with transaction.atomic():
            if template.pk:
                old_name = TrainingLogTemplate.objects.select_for_update().get(pk=template.pk).file.name
            # 未替换文件时不重复读取现有文件，仍校验其余模型字段。
            template.full_clean(exclude=None if upload else ["file"])
            template.save()
            if old_name and old_name != template.file.name:
                transaction.on_commit(lambda: storage.delete(old_name), robust=True)
    except Exception:
        if upload and template.file._committed and template.file.name != old_name:
            storage.delete(template.file.name)
        raise
    return template


@transaction.atomic
def delete_log_template(template, *, actor):
    require_template_permission(actor, "delete")
    TrainingLogTemplate.objects.select_for_update().get(pk=template.pk).delete()
