from django import forms
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils import timezone

from core.constants import CONDUCT_SEVERITY_MODERATE
from core.utils.mixins import CreatedUpdatedAdminMixin

from .models import (
    ConductCategory,
    ConductItem,
    ConductRecord,
    ConductSeverityRule,
    ConductSummary,
    format_conduct_score,
    get_conduct_severity_choices,
)


SEVERITY_PLACEHOLDER_LABEL = '请先选择奖惩事项'


def get_record_severity_choices(nature=None):
    if not nature:
        return [('', SEVERITY_PLACEHOLDER_LABEL)]

    return get_conduct_severity_choices(nature)


def get_widget_attr_target(widget):
    return getattr(widget, 'widget', widget)


class ConductAuditAdminMixin(CreatedUpdatedAdminMixin):
    @admin.display(description='创建人')
    def created_by_display(self, obj):
        return obj.created_by.full_info if obj.created_by else '-'

    @admin.display(description='更新人')
    def updated_by_display(self, obj):
        return obj.updated_by.full_info if obj.updated_by else '-'


class ConductSeverityRuleAdminForm(forms.ModelForm):
    class Meta:
        model = ConductSeverityRule
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nature = self.data.get('nature') or getattr(self.instance, 'nature', None)
        self.fields['severity'].choices = get_conduct_severity_choices(nature)


class ConductRecordAdminForm(forms.ModelForm):
    class Meta:
        model = ConductRecord
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        item_id = self.data.get('item') or getattr(self.instance, 'item_id', None)
        nature = None

        if item_id:
            item = ConductItem.objects.filter(pk=item_id).select_related('category').first()
            if item is not None:
                nature = item.category.nature

        self.fields['severity'].choices = get_record_severity_choices(nature)
        if nature is None:
            self.fields['severity'].initial = ''
            self.initial['severity'] = ''


@admin.register(ConductCategory)
class ConductCategoryAdmin(ConductAuditAdminMixin, admin.ModelAdmin):
    list_display = [
        'name',
        'nature',
        'order',
        'is_active',
        'created_by_display',
        'created_at',
        'updated_by_display',
        'updated_at',
    ]
    list_filter = ['nature', 'is_active', 'created_by', 'updated_by', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_by', 'updated_at']
    ordering = ['nature', 'order', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('nature', 'name', 'description', 'order')
        }),
        ('状态', {
            'fields': ('is_active',)
        }),
        ('元数据', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ConductItem)
class ConductItemAdmin(ConductAuditAdminMixin, admin.ModelAdmin):
    list_display = [
        'name',
        'category',
        'default_score',
        'is_active',
        'created_by_display',
        'created_at',
        'updated_by_display',
        'updated_at',
    ]
    list_filter = ['category__nature', 'category', 'is_active', 'created_by', 'updated_by', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_by', 'updated_at']
    ordering = ['category__nature', 'category__order', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('category', 'name', 'default_score', 'description'),
            'description': '当前分值 = 事项默认分值 × 严重程度系数。一般情形按默认分值计分。'
        }),
        ('状态', {
            'fields': ('is_active',)
        }),
        ('元数据', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ConductSeverityRule)
class ConductSeverityRuleAdmin(ConductAuditAdminMixin, admin.ModelAdmin):
    form = ConductSeverityRuleAdminForm
    list_display = [
        'nature',
        'severity_display',
        'multiplier_display',
        'order',
        'created_by_display',
        'created_at',
        'updated_by_display',
        'updated_at',
    ]
    list_filter = ['nature', 'severity', 'created_by', 'updated_by', 'created_at', 'updated_at']
    search_fields = ['nature', 'severity']
    readonly_fields = ['created_by', 'created_at', 'updated_by', 'updated_at']
    ordering = ['nature', 'order', 'severity']

    fieldsets = (
        ('基本信息', {
            'fields': ('nature', 'severity', 'multiplier', 'order'),
            'description': '当前分值 = 事项默认分值 × 严重程度系数。修改系数后，相关历史记录与汇总会同步重算。',
        }),
        ('元数据', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='系数')
    def multiplier_display(self, obj):
        return f'{obj.multiplier:.2f}倍'

    @admin.display(description='严重程度')
    def severity_display(self, obj):
        return obj.severity_label

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConductRecord)
class ConductRecordAdmin(admin.ModelAdmin):
    form = ConductRecordAdminForm
    record_fields = ('student', 'item', 'severity', 'occurred_date', 'reason', 'attachment')
    review_fields = ('status', 'review_note', 'reviewed_by', 'reviewed_at')
    metadata_fields = ('recorded_by', 'recorded_at', 'updated_by', 'updated_at')

    list_display = [
        'student_display',
        'item',
        'severity_display',
        'score_display',
        'occurred_date',
        'status',
        'recorded_by_display',
        'updated_by_display',
        'reviewed_by_display',
        'updated_at',
        'recorded_at'
    ]
    list_filter = [
        'status',
        'item__category__nature',
        'item__category',
        'severity',
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
    readonly_fields = ['recorded_by', 'recorded_at', 'updated_by', 'updated_at', 'reviewed_by', 'reviewed_at']
    date_hierarchy = 'occurred_date'

    class Media:
        js = ('behaviors/js/conduct_record_admin.js',)

    def _can_record(self, request):
        return request.user.is_superuser or request.user.has_perm('behaviors.add_conduct_record')

    def _can_review(self, request):
        return request.user.is_superuser or request.user.has_perm('behaviors.review_conduct_record')

    def _can_view_all(self, request):
        return (
            request.user.is_superuser
            or request.user.has_perm('behaviors.view_all_conduct_records')
            or request.user.has_perm('behaviors.view_conductrecord')
            or request.user.has_perm('behaviors.change_conductrecord')
            or request.user.has_perm('behaviors.delete_conductrecord')
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
            'updated_by',
            'reviewed_by',
        )

        if self._can_view_all(request):
            return queryset

        if self._can_record(request):
            return queryset.filter(recorded_by=request.user)

        return queryset.none()

    def get_urls(self):
        return [
            path(
                'severity-choices/',
                self.admin_site.admin_view(self.severity_choices_view),
                name='behaviors_conductrecord_severity_choices',
            ),
        ] + super().get_urls()

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)

        if 'item' in form.base_fields:
            item_widget = get_widget_attr_target(form.base_fields['item'].widget)
            item_widget.attrs['data-severity-choices-url'] = reverse(
                'admin:behaviors_conductrecord_severity_choices',
            )

        if 'severity' in form.base_fields:
            severity_widget = get_widget_attr_target(form.base_fields['severity'].widget)
            severity_widget.attrs['data-default-severity'] = CONDUCT_SEVERITY_MODERATE
            severity_widget.attrs['data-placeholder-label'] = SEVERITY_PLACEHOLDER_LABEL

        return form

    def severity_choices_view(self, request):
        item_id = request.GET.get('item_id')
        nature = None

        if item_id:
            item = ConductItem.objects.filter(pk=item_id).select_related('category').first()
            if item is not None:
                nature = item.category.nature

        choices = [
            {'value': value, 'label': label}
            for value, label in get_record_severity_choices(nature)
        ]
        return JsonResponse({
            'choices': choices,
            'default': CONDUCT_SEVERITY_MODERATE,
        })

    def get_fieldsets(self, request, obj=None):
        basic_fields = self.record_fields
        if obj is not None:
            basic_fields = self.record_fields + ('score_formula_display',)

        fieldsets = [
            ('基本信息', {
                'fields': basic_fields,
                'description': '当前分值 = 事项默认分值 × 严重程度系数。默认“一般”档会按事项默认分值计分。',
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
        all_fields = self.record_fields + self.review_fields + self.metadata_fields + ('score_formula_display',)

        if obj is not None and not self.has_change_permission(request, obj):
            return all_fields

        readonly_fields = list(self.readonly_fields)

        if obj is not None:
            readonly_fields.append('score_formula_display')

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

    @admin.display(description='严重程度')
    def severity_display(self, obj):
        return obj.severity_label

    @admin.display(description='当前分值')
    def score_display(self, obj):
        return format_conduct_score(obj.score)

    @admin.display(description='计分说明')
    def score_formula_display(self, obj):
        return obj.score_formula or '-'

    @admin.display(description='记录人')
    def recorded_by_display(self, obj):
        return obj.recorded_by.full_info if obj.recorded_by else '-'

    @admin.display(description='更新人')
    def updated_by_display(self, obj):
        return obj.updated_by.full_info if obj.updated_by else '-'

    @admin.display(description='审核人')
    def reviewed_by_display(self, obj):
        return obj.reviewed_by.full_info if obj.reviewed_by else '-'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
            obj.status = ConductRecord.STATUS_PENDING
        else:
            obj.updated_by = request.user
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
