from django.contrib import admin
from .models import ConductType, ConductRecord, ConductSummary


@admin.register(ConductType)
class ConductTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'score', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'category', 'score', 'description')
        }),
        ('状态', {
            'fields': ('is_active',)
        }),
        ('元数据', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # 创建时
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ConductRecord)
class ConductRecordAdmin(admin.ModelAdmin):
    list_display = [
        'student',
        'record_type',
        'occurred_date',
        'score',
        'status',
        'recorded_by',
        'reviewed_by'
    ]
    list_filter = ['status', 'record_type__category', 'occurred_date', 'recorded_at']
    search_fields = [
        'student__username',
        'student__first_name',
        'reason',
        'review_note'
    ]
    readonly_fields = [
        'recorded_by',
        'recorded_at',
        'reviewed_by',
        'reviewed_at'
    ]
    date_hierarchy = 'occurred_date'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('student', 'record_type', 'occurred_date', 'reason')
        }),
        ('附件', {
            'fields': ('attachment',)
        }),
        ('审核信息', {
            'fields': ('status', 'review_note', 'reviewed_by', 'reviewed_at')
        }),
        ('元数据', {
            'fields': ('recorded_by', 'recorded_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # 创建时
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ConductSummary)
class ConductSummaryAdmin(admin.ModelAdmin):
    list_display = [
        'student',
        'total_score',
        'reward_count',
        'penalty_count',
        'last_updated'
    ]
    list_filter = ['last_updated']
    search_fields = ['student__username', 'student__first_name']
    readonly_fields = [
        'student',
        'total_score',
        'reward_count',
        'penalty_count',
        'last_updated'
    ]
    
    def has_add_permission(self, request):
        """不允许手动添加汇总记录"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """不允许删除汇总记录"""
        return False
        # return super().has_delete_permission(request, obj)
