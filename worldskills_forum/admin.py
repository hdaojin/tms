from django.contrib import admin

from core.utils.mixins import CreatedUpdatedAdminMixin

from .models import ForumCategory, ForumModule, ForumPost, ForumPostAttachment, ForumSourceRole, ForumTag, ForumTopic, ForumTopicReadState, ForumTranslation


@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name", "slug")


@admin.register(ForumTag)
class ForumTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "updated_at")
    search_fields = ("name", "slug")


@admin.register(ForumModule)
class ForumModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name", "slug")


@admin.register(ForumSourceRole)
class ForumSourceRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active", "is_official", "allows_detail")
    list_editable = ("sort_order", "is_active", "is_official", "allows_detail")
    search_fields = ("name", "slug")


@admin.register(ForumTopic)
class ForumTopicAdmin(CreatedUpdatedAdminMixin, admin.ModelAdmin):
    list_display = ("translated_title", "competition_year", "module", "category", "status", "importance", "updated_at")
    list_filter = ("competition_year", "module", "category", "status", "importance")
    search_fields = ("translated_title", "original_title", "summary", "source_topic_id")
    filter_horizontal = ("tags",)


class ExistingOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False


@admin.register(ForumPost)
class ForumPostAdmin(ExistingOnlyAdmin):
    list_display = ("topic", "author_name", "source_role", "post_type", "importance", "posted_at")
    list_filter = ("source_role", "post_type", "importance")
    search_fields = ("topic__translated_title", "author_name", "original_content", "source_post_id")


@admin.register(ForumTranslation)
class ForumTranslationAdmin(ExistingOnlyAdmin):
    list_display = ("post", "translated_by", "published_at", "updated_at")
    search_fields = ("post__topic__translated_title", "translated_content")

    def delete_model(self, request, obj):
        obj.post.delete()

    def delete_queryset(self, request, queryset):
        ForumPost.objects.filter(pk__in=queryset.values("post_id")).delete()


@admin.register(ForumPostAttachment)
class ForumPostAttachmentAdmin(ExistingOnlyAdmin):
    list_display = ("post", "kind", "original_filename", "file_size", "source_url", "created_by", "created_at")
    search_fields = ("original_filename", "caption_zh", "source_url", "post__topic__translated_title")
    readonly_fields = ("post", "file", "file_size", "content_type", "created_by", "created_at")


@admin.register(ForumTopicReadState)
class ForumTopicReadStateAdmin(admin.ModelAdmin):
    list_display = ("user", "topic", "last_viewed_at")
    search_fields = ("user__username", "topic__translated_title")
