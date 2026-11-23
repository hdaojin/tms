from django.contrib import admin

from .models import ConductCategory, ConductItem, ConductRecord, ConductSeverity, ConductSeverityRule
from .permissions import can_manage_catalog, can_record_conduct, can_view_all_conduct_records
from .selectors import can_view_records, visible_records


class ReadOnlyConductAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CatalogAdmin(ReadOnlyConductAdmin):
    def has_module_permission(self, request):
        return can_manage_catalog(request.user)

    def has_view_permission(self, request, obj=None):
        return can_manage_catalog(request.user)


@admin.register(ConductCategory)
class ConductCategoryAdmin(CatalogAdmin):
    list_display = ('code', 'name', 'nature', 'order', 'is_active', 'created_by', 'updated_by')
    list_filter = ('nature', 'is_active')
    search_fields = ('code', 'name')


@admin.register(ConductItem)
class ConductItemAdmin(CatalogAdmin):
    list_display = ('code', 'name', 'category', 'default_score', 'is_active', 'created_by', 'updated_by')
    list_filter = ('category', 'is_active')
    search_fields = ('code', 'name')
    list_select_related = ('category', 'created_by', 'updated_by')


@admin.register(ConductSeverity)
class ConductSeverityAdmin(CatalogAdmin):
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)


@admin.register(ConductSeverityRule)
class ConductSeverityRuleAdmin(CatalogAdmin):
    list_display = ('nature', 'severity', 'label', 'multiplier', 'is_default', 'created_by', 'updated_by')
    list_filter = ('nature', 'severity')
    list_select_related = ('severity', 'created_by', 'updated_by')


@admin.register(ConductRecord)
class ConductRecordAdmin(ReadOnlyConductAdmin):
    list_display = ('occurred_date', 'cycle', 'student', 'item_label', 'severity_label', 'frozen_points', 'status')
    list_filter = ('cycle', 'status', 'frozen_nature')
    search_fields = ('student__first_name', 'student__last_name', 'item_label')
    list_select_related = ('cycle', 'student')
    exclude = ('attachment', 'submission_key', 'source_cycle_record_id')

    def has_module_permission(self, request):
        user = request.user
        return user.is_active and (
            can_view_records(user) or (user.is_staff and (can_record_conduct(user) or can_view_all_conduct_records(user)))
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request) if obj is None else self.get_queryset(request).filter(pk=obj.pk).exists()

    def get_queryset(self, request):
        return visible_records(request.user, legacy_admin=True)

    def get_readonly_fields(self, request, obj=None):
        snapshots = ('frozen_points', 'category_label', 'item_label', 'severity_label', 'recorded_at', 'updated_at')
        if not obj or not obj.attachment or not visible_records(request.user).filter(pk=obj.pk).exists():
            return snapshots
        return (*snapshots, 'attachment_link')

    @admin.display(description='附件')
    def attachment_link(self, record):
        if not record.attachment:
            return '—'
        from django.urls import reverse
        from django.utils.html import format_html

        return format_html('<a href="{}">下载附件</a>', reverse('behaviors:conduct_attachment', args=[record.pk]))
