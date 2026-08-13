from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import SkillProject, SkillTreeVersion


@transaction.atomic
def set_current_skill_tree_version(version: SkillTreeVersion) -> SkillTreeVersion:
    """Atomically make one existing version current for its skill project."""
    if not version.pk or not version.skill_project_id:
        raise ValidationError("只能切换已经保存且属于技能项目的技能树版本。")

    SkillProject.objects.select_for_update().get(pk=version.skill_project_id)
    target = SkillTreeVersion.objects.select_for_update().get(pk=version.pk)
    if target.skill_project_id != version.skill_project_id:
        raise ValidationError("技能树版本与技能项目不一致。")

    SkillTreeVersion.objects.filter(
        skill_project_id=target.skill_project_id,
        is_current=True,
    ).exclude(pk=target.pk).update(is_current=False)
    target.is_current = True
    target.save(update_fields=["is_current", "updated_at"])
    return target
