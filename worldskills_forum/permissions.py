from django.http import Http404


def can_edit_topic(user, topic) -> bool:
    return bool(user.is_superuser or user.has_perm("worldskills_forum.change_forumtopic") or topic.created_by_id == user.pk)


def can_edit_post(user, post) -> bool:
    return bool(
        user.is_superuser
        or (user.has_perm("worldskills_forum.change_forumpost") and user.has_perm("worldskills_forum.change_forumtranslation"))
        or post.created_by_id == user.pk
        or getattr(getattr(post, "translation", None), "translated_by_id", None) == user.pk
    )


class OwnerOrChangePermissionMixin:
    permission_name = ""
    owner_field = "created_by"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        if user.is_superuser or (self.permission_name and user.has_perm(self.permission_name)):
            return obj
        if getattr(obj, f"{self.owner_field}_id", None) == user.pk:
            return obj
        raise Http404
