from django.contrib import admin
from .models import ConductCategory, ConductItem, ConductRecord, ConductSummary


@admin.register(ConductCategory)
class ConductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'nature', 'order', 'is_active', 'created_at']
    list_filter = ['nature', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['nature', 'order', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('nature', 'name', 'description', 'order')
        }),
        ('状态', {
            'fields': ('is_active',)
        }),
    )


@admin.register(ConductItem)
class ConductItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'score', 'is_active', 'created_at']
    list_filter = ['category__nature', 'category', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    ordering = ['category__nature', 'category__order', '-score', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('category', 'name', 'score', 'description')
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
        'item',
        'occurred_date',
        'status',
        'recorded_by',
        'reviewed_by',
        'recorded_at'
    ]
    list_filter = [
        'status',
        'item__category__nature',
        'item__category',
        'occurred_date',
        'recorded_at'
    ]
    search_fields = [
        'student__username',
        'student__first_name',
        'student__last_name',
        'reason'
    ]
    readonly_fields = ['recorded_by', 'recorded_at', 'reviewed_by', 'reviewed_at']
    date_hierarchy = 'occurred_date'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('student', 'item', 'occurred_date', 'reason', 'attachment')
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
    search_fields = [
        'student__username',
        'student__first_name',
        'student__last_name'
    ]
    readonly_fields = [
        'student',
        'total_score',
        'reward_count',
        'penalty_count',
        'last_updated'
    ]
    
    def has_add_permission(self, request):
        # 汇总表由系统自动创建，不允许手动添加
        return False
