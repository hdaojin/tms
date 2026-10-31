from django.contrib import admin
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .permissions import (
    can_access_meeting_admin_module,
    can_change_meeting_admin,
    can_delete_meeting,
    can_upload_meeting,
    can_view_meeting_admin,
)
from .models import Meeting
from .services import save_meeting
from .forms import MeetingUploadForm
from .selectors import meeting_queryset_for

# Register your models here.


class MeetingAdmin(admin.ModelAdmin):
    form = MeetingUploadForm
    list_display = ('title', 'date', 'filename', 'uploaded_by', 'uploaded_at', 'is_public')
    search_fields = ('title', 'file', 'uploaded_by__username')
    list_filter = ('date', ('uploaded_by', admin.RelatedOnlyFieldListFilter))
    date_hierarchy = 'date'
    ordering = ('-date',)
    readonly_fields = ('uploaded_by', 'uploaded_at')
    fields = ('title', 'date', 'file', 'is_public', 'visible_groups', 'visible_users', 'uploaded_by', 'uploaded_at')

    def get_fields(self, request, obj=None):
        fields = list(self.fields)
        if obj is not None and not can_change_meeting_admin(request.user, obj):
            fields = [field for field in fields if field not in ('visible_groups', 'visible_users')]
        return fields

    def get_queryset(self, request):
        return meeting_queryset_for(request.user, super().get_queryset(request))

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        if obj is None:
            raise Http404
        return obj

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
        cleaned = form.cleaned_data if form is not None else {}
        file = obj.file if obj.file and not obj.file._committed else None
        save_meeting(
            meeting=obj,
            actor=request.user,
            change=change,
            is_public=cleaned.get('is_public', obj.is_public),
            group_ids=[group.pk for group in cleaned['visible_groups']] if 'visible_groups' in cleaned else (),
            user_ids=[user.pk for user in cleaned['visible_users']] if 'visible_users' in cleaned else (),
        )
        if file is not None:
            if not hasattr(request, '_meeting_new_files'):
                request._meeting_new_files = []
            request._meeting_new_files.append(file)

    def save_related(self, request, form, formsets, change):
        # 两组受众已由 service 在同一事务保存，不让默认 save_m2m 覆盖清空结果。
        for formset in formsets:
            self.save_formset(request, form, formset, change)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except Exception:
            # Admin 外层事务还包含日志等后续保存，失败时同样清理新文件。
            for file in getattr(request, '_meeting_new_files', []):
                file.storage.delete(file.name)
            raise

    def delete_queryset(self, request, queryset):
        if not can_delete_meeting(request.user):
            raise PermissionDenied
        with transaction.atomic():
            ids = list(queryset.values_list('pk', flat=True))
            current = meeting_queryset_for(request.user).select_for_update().filter(pk__in=ids)
            if current.count() != len(ids):
                raise Http404
            current.delete()


# 向默认admin站点注册
admin.site.register(Meeting, MeetingAdmin)
