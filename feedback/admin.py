from django.contrib import admin

from .models import Feedback, FeedbackAttachment, FeedbackReply


class FeedbackReplyInline(admin.TabularInline):
    model = FeedbackReply
    extra = 0
    fields = ("author", "content", "created_at")
    readonly_fields = ("created_at",)


class FeedbackAttachmentInline(admin.TabularInline):
    model = FeedbackAttachment
    extra = 0
    fields = ("reply", "original_filename", "file", "file_size", "content_type", "uploaded_by", "created_at")
    readonly_fields = ("file_size", "content_type", "uploaded_by", "created_at")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("pk", "category", "title", "status", "is_anonymous", "is_private", "created_at", "updated_at")
    list_filter = ("category", "status", "is_private", "is_anonymous")
    search_fields = ("title", "content")
    readonly_fields = ("created_at", "updated_at", "resolved_at")
    inlines = (FeedbackReplyInline, FeedbackAttachmentInline)


@admin.register(FeedbackReply)
class FeedbackReplyAdmin(admin.ModelAdmin):
    list_display = ("feedback", "author", "created_at")
    search_fields = ("feedback__title", "content")
    readonly_fields = ("created_at",)


@admin.register(FeedbackAttachment)
class FeedbackAttachmentAdmin(admin.ModelAdmin):
    list_display = ("feedback", "reply", "original_filename", "file_size", "uploaded_by", "created_at")
    search_fields = ("original_filename", "feedback__title")
    list_filter = ("created_at",)
    readonly_fields = ("file_size", "content_type", "uploaded_by", "created_at")
