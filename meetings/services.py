from __future__ import annotations

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Meeting
from .permissions import can_change_meeting_admin, can_upload_meeting
from .selectors import recipient_queryset


def prepare_meeting_for_save(meeting, *, actor, change):
    if not change and not meeting.uploaded_by_id:
        meeting.uploaded_by = actor
    return meeting


def validate_audience(*, is_public, group_ids, user_ids, existing_user_ids=()):
    if not isinstance(is_public, bool):
        raise ValidationError("请选择有效的可见范围。")
    if is_public:
        return set(), set()
    try:
        group_ids, user_ids = list(group_ids), list(user_ids)
        if any(not str(pk).isdecimal() for pk in [*group_ids, *user_ids]):
            raise ValueError
        group_ids = {int(pk) for pk in group_ids}
        user_ids = {int(pk) for pk in user_ids}
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError("可见角色或人员无效，请重新选择。") from exc
    if not group_ids and not user_ids:
        raise ValidationError("取消“所有人”后，请至少选择一个角色或指定人员。")
    if set(Group.objects.filter(pk__in=group_ids).values_list("pk", flat=True)) != group_ids:
        raise ValidationError("可见角色已变化，请重新选择。")
    newly_selected = user_ids - set(existing_user_ids)
    if set(recipient_queryset().filter(pk__in=newly_selected).values_list("pk", flat=True)) != newly_selected:
        raise ValidationError("指定人员已停用或没有会议查看权限，请重新选择。")
    return group_ids, user_ids


def save_meeting(*, meeting, actor, is_public, group_ids, user_ids, change=False, audience_only=False):
    """上传、后台保存和受众设置的统一事务入口，不修改账号的角色或权限。"""
    new_file = meeting.file if meeting.file and not meeting.file._committed else None
    try:
        with transaction.atomic():
            actor = get_user_model().objects.filter(pk=getattr(actor, "pk", None), is_active=True).first()
            if actor is None:
                raise PermissionDenied
            existing_ids = ()
            if change:
                current = get_object_or_404(Meeting.objects.select_for_update(), pk=meeting.pk)
                if not can_change_meeting_admin(actor):
                    raise PermissionDenied
                if not can_change_meeting_admin(actor, current):
                    raise Http404
                existing_ids = current.visible_users.values_list("pk", flat=True)
                if audience_only:
                    meeting = current
                else:
                    meeting.uploaded_by_id = current.uploaded_by_id
                    meeting.uploaded_at = current.uploaded_at
            elif not can_upload_meeting(actor):
                raise PermissionDenied
            groups, users = validate_audience(
                is_public=is_public, group_ids=group_ids, user_ids=user_ids, existing_user_ids=existing_ids
            )
            meeting.is_public = is_public
            prepare_meeting_for_save(meeting, actor=actor, change=change)
            if audience_only:
                meeting.save(update_fields=["is_public"])
            else:
                meeting.full_clean()
                meeting.save()
            meeting.visible_groups.set(groups)
            meeting.visible_users.set(users)
        return meeting
    except Exception:
        # 数据库事务不能回滚 storage；只删除此次已写出的新文件。
        if new_file is not None and new_file._committed and new_file.name:
            new_file.storage.delete(new_file.name)
        raise
