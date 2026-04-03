from django.contrib import admin
from django.utils import timezone

from .models import ConductCategory, ConductItem, ConductRecord, ConductSummary


@admin.register(ConductCategory)
class ConductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'nature', 'order', 'is_active', 'created_at']
    list_filter = ['nature', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['nature', 'order', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('nature', 'name', 'description', 'order')
        }),
        ('状态', {
            'fields': ('is_active',)
        }),
        ('元数据', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
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
            'fields': ('category', 'name', 'score', 'description'),
            'description': '修改事项分值会同步影响历史记录与汇总。'
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
    record_fields = ('student', 'item', 'occurred_date', 'reason', 'attachment')
    review_fields = ('status', 'review_note', 'reviewed_by', 'reviewed_at')
    metadata_fields = ('recorded_by', 'recorded_at')

    list_display = [
        'student_display',
        'item',
        'score_display',
        'occurred_date',
        'status',
        'recorded_by_display',
        'reviewed_by_display',
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
        'item__name',
        'reason'
    ]
    readonly_fields = ['recorded_by', 'recorded_at', 'reviewed_by', 'reviewed_at']
    date_hierarchy = 'occurred_date'

    def _can_record(self, request):
        return request.user.is_superuser or request.user.has_perm('conduct.add_conduct_record')

    def _can_review(self, request):
        return request.user.is_superuser or request.user.has_perm('conduct.review_conduct_record')

    def _can_view_all(self, request):
        return (
            request.user.is_superuser
            or request.user.has_perm('conduct.view_all_conduct_records')
            or request.user.has_perm('conduct.view_conductrecord')
            or request.user.has_perm('conduct.change_conductrecord')
            or request.user.has_perm('conduct.delete_conductrecord')
            or self._can_review(request)
        )

    def has_module_permission(self, request):
        return self._can_record(request) or self._can_review(request) or self._can_view_all(request)

    def has_view_permission(self, request, obj=None):
        if not self.has_module_permission(request):
            return False

        if obj is None or self._can_view_all(request):
            return True

        return self._can_record(request) and obj.recorded_by_id == request.user.id

    def has_add_permission(self, request):
        return self._can_record(request)

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return self._can_record(request) or self._can_review(request)

        if not self.has_view_permission(request, obj):
            return False

        if obj.status != ConductRecord.STATUS_PENDING:
            return False

        if self._can_review(request):
            return True

        return self._can_record(request) and obj.recorded_by_id == request.user.id

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            'student',
            'item__category',
            'recorded_by',
            'reviewed_by',
        )

        if self._can_view_all(request):
            return queryset

        if self._can_record(request):
            return queryset.filter(recorded_by=request.user)

        return queryset.none()

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ('基本信息', {
                'fields': self.record_fields,
                'description': '记录分值始终跟随当前事项分值。修改事项分值会同步影响历史记录与汇总。',
            }),
        ]

        if obj is not None:
            fieldsets.append(('审核信息', {'fields': self.review_fields}))
            fieldsets.append(('元数据', {
                'fields': self.metadata_fields,
                'classes': ('collapse',),
            }))

        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        all_fields = self.record_fields + self.review_fields + self.metadata_fields

        if obj is not None and not self.has_change_permission(request, obj):
            return all_fields

        readonly_fields = list(self.readonly_fields)

        if obj is None:
            return readonly_fields + ['status', 'review_note']

        if self._can_record(request) and not self._can_review(request):
            return readonly_fields + ['status', 'review_note']

        if self._can_review(request) and not self._can_record(request):
            return readonly_fields + list(self.record_fields)

        return readonly_fields

    @admin.display(description='学生')
    def student_display(self, obj):
        return obj.student.full_info

    @admin.display(description='当前分值')
    def score_display(self, obj):
        return f'{obj.score:+.2f}'

    @admin.display(description='记录人')
    def recorded_by_display(self, obj):
        return obj.recorded_by.full_info if obj.recorded_by else '-'

    @admin.display(description='审核人')
    def reviewed_by_display(self, obj):
        return obj.reviewed_by.full_info if obj.reviewed_by else '-'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
            obj.status = ConductRecord.STATUS_PENDING
        else:
            original_status = ConductRecord.objects.filter(pk=obj.pk).values_list('status', flat=True).first()
            if (
                original_status == ConductRecord.STATUS_PENDING
                and obj.status in [ConductRecord.STATUS_APPROVED, ConductRecord.STATUS_REJECTED]
            ):
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()

        super().save_model(request, obj, form, change)


@admin.register(ConductSummary)
class ConductSummaryAdmin(admin.ModelAdmin):
    list_display = [
        'student_display',
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

    @admin.display(description='学生')
    def student_display(self, obj):
        return obj.student.full_info
    
    def has_add_permission(self, request):
        # 汇总表由系统自动创建，不允许手动添加
        return False

    def has_delete_permission(self, request, obj=None):
        return False
