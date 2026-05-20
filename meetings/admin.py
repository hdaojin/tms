from django.contrib import admin

from .permissions import (
    can_access_meeting_admin_module,
    can_change_meeting_admin,
    can_delete_meeting,
    can_upload_meeting,
    can_view_meeting_admin,
)
from .models import Meeting
from .services import prepare_meeting_for_save

# Register your models here.

class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'filename', 'uploaded_by', 'uploaded_at')
    search_fields = ('title', 'filename', 'uploaded_by__username')
    list_filter = ('date', 'uploaded_by')
    date_hierarchy = 'date'
    ordering = ('-date',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uploaded_by')

    def has_module_permission(self, request):
        return can_access_meeting_admin_module(request.user)

    def has_view_permission(self, request, obj=None):
        return can_view_meeting_admin(request.user, obj)

    def has_add_permission(self, request):
        return can_upload_meeting(request.user)

    def has_change_permission(self, request, obj=None):
        return can_change_meeting_admin(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        return can_delete_meeting(request.user, obj)

    def save_model(self, request, obj, form, change):
        prepare_meeting_for_save(obj, actor=request.user, change=change)
        super().save_model(request, obj, form, change)

# 向默认admin站点注册
admin.site.register(Meeting, MeetingAdmin)