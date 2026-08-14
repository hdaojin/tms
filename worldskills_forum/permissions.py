from django.http import Http404


def can_edit_topic(user, topic) -> bool:
    return bool(
        user.has_perm("worldskills_forum.change_forumtopic")
        and (
            user.has_perm("worldskills_forum.change_all_forum_content")
            or topic.created_by_id == user.pk
        )
    )


def can_edit_post(user, post) -> bool:
    return bool(
        user.has_perm("worldskills_forum.change_forumpost")
        and user.has_perm("worldskills_forum.change_forumtranslation")
        and (
            user.has_perm("worldskills_forum.change_all_forum_content")
            or post.created_by_id == user.pk
            or getattr(getattr(post, "translation", None), "translated_by_id", None) == user.pk
        )
    )


class OwnerOrChangePermissionMixin:
    permission_name = ""
    owner_field = "created_by"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        if not self.permission_name or not user.has_perm(self.permission_name):
            raise Http404
        if user.has_perm("worldskills_forum.change_all_forum_content"):
            return obj
        if getattr(obj, f"{self.owner_field}_id", None) == user.pk:
            return obj
        raise Http404
