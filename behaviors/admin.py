from django import forms
from django.contrib import admin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import path, reverse

from core.utils.mixins import CreatedUpdatedAdminMixin
from .forms import configure_severity_field
from .models import (
    ConductCategory,
    ConductItem,
    ConductNature,
    ConductRecord,
    ConductSeverity,
    ConductSeverityRule,
    ConductSummary,
    format_conduct_score,
    get_conduct_severity_choices_with_multiplier,
    get_default_conduct_severity,
)
from .permissions import (
    can_access_conduct_record_admin_module,
    can_change_conduct_record_admin,
    can_record_conduct,
    can_review_conduct,
    can_view_all_conduct_records,
    can_view_conduct_record_admin,
)
from .selectors import get_conduct_record_admin_queryset
from .services import prepare_conduct_record_for_save


SEVERITY_PLACEHOLDER_LABEL = '请先选择奖惩事项'


def get_record_severity_choices(nature=None, *, current_severity_id=None):
    if not nature:
        return [('', SEVERITY_PLACEHOLDER_LABEL)]

    return get_conduct_severity_choices_with_multiplier(
        nature,
        current_severity_id=current_severity_id,
    )


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
        current_severity_id = self.instance.severity_id if self.instance.pk else None
        self.fields['severity'].to_field_name = 'code'
        self.fields['severity'].queryset = ConductSeverity.objects.filter(
            Q(is_active=True) | Q(pk=current_severity_id)
        ).order_by('code')


class ConductItemAdminForm(forms.ModelForm):
    class Meta:
        model = ConductItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = ConductCategory.objects.filter(
            is_active=True,
            nature__in=ConductNature.values,
        )
        if self.instance.pk and self.instance.category_id:
            queryset = ConductCategory.objects.filter(
                Q(is_active=True, nature__in=ConductNature.values)
                | Q(pk=self.instance.category_id)
            )
        self.fields['category'].queryset = queryset.order_by('nature', 'order', 'name')


class ConductRecordAdminForm(forms.ModelForm):
    class Meta:
        model = ConductRecord
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        item_id = self.data.get('item') or getattr(self.instance, 'item_id', None)
        nature = None
        current_item_id = self.instance.item_id if self.instance.pk else None
        item_queryset = ConductItem.objects.filter(
            is_active=True,
            category__is_active=True,
            category__nature__in=ConductNature.values,
        )
        if current_item_id:
            item_queryset = ConductItem.objects.filter(
                Q(
                    is_active=True,
                    category__is_active=True,
                    category__nature__in=ConductNature.values,
                )
                | Q(pk=current_item_id)
            )
        self.fields['item'].queryset = item_queryset.select_related('category')

        if item_id:
            item = item_queryset.filter(pk=item_id).select_related('category').first()
            if item is not None:
                nature = item.category.nature

        current_severity_id = self.instance.severity_id if self.instance.pk else None
        default_code = configure_severity_field(
            self.fields['severity'],
            nature,
            current_severity_id=current_severity_id,
        )
        if nature is None:
            self.fields['severity'].empty_label = SEVERITY_PLACEHOLDER_LABEL
        elif not self.is_bound and not self.instance.pk and default_code:
            self.fields['severity'].initial = default_code


@admin.register(ConductCategory)
class ConductCategoryAdmin(ConductAuditAdminMixin, admin.ModelAdmin):
    list_display = [
        'code',
        'name',
        'nature_display',
        'order',
        'is_active',
        'created_by_display',
        'created_at',
        'updated_by_display',
        'updated_at',
    ]
    list_filter = ['nature', 'is_active', 'created_by', 'updated_by', 'created_at', 'updated_at']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_by', 'updated_at']
    ordering = ['nature', 'order', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('code', 'nature', 'name', 'description', 'order')
        }),
        ('状态', {
            'fields': ('is_active',)
        }),
        ('元数据', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        if obj is not None:
            readonly_fields.append('code')
            if obj.nature not in ConductNature.values:
                readonly_fields.append('nature')
        return readonly_fields

    @admin.display(description='性质', ordering='nature')
    def nature_display(self, obj):
        return obj.nature_label


@admin.register(ConductSeverity)
class ConductSeverityAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['created_at', 'updated_at']

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        if obj is not None:
            readonly_fields.append('code')
        return readonly_fields


@admin.register(ConductItem)
class ConductItemAdmin(ConductAuditAdminMixin, admin.ModelAdmin):
    form = ConductItemAdminForm
    list_display = [
        'code',
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
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_by', 'updated_at']
    ordering = ['category__nature', 'category__order', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('category', 'code', 'name', 'default_score', 'description'),
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

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        if obj is not None:
            readonly_fields.append('code')
        return readonly_fields


@admin.register(ConductSeverityRule)
class ConductSeverityRuleAdmin(ConductAuditAdminMixin, admin.ModelAdmin):
    form = ConductSeverityRuleAdminForm
    list_display = [
        'nature_display',
        'severity_display',
        'label',
        'multiplier_display',
        'order',
        'is_default',
        'created_by_display',
        'created_at',
        'updated_by_display',
        'updated_at',
    ]
    list_filter = ['nature', 'severity', 'created_by', 'updated_by', 'created_at', 'updated_at']
    search_fields = ['nature', 'severity__code', 'severity__name', 'label']
    readonly_fields = ['created_by', 'created_at', 'updated_by', 'updated_at']
    ordering = ['nature', 'order', 'severity']

    fieldsets = (
        ('基本信息', {
            'fields': ('nature', 'severity', 'label', 'multiplier', 'order', 'is_default'),
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
        return obj.severity.name

    @admin.display(description='性质', ordering='nature')
    def nature_display(self, obj):
        return obj.nature_label

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        if obj is not None and obj.nature not in ConductNature.values:
            readonly_fields.append('nature')
        return readonly_fields

    @staticmethod
    def is_used_by_conduct_records(obj):
        return ConductRecord.objects.filter(
            item__category__nature=obj.nature,
            severity_id=obj.severity_id,
        ).exists()

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        return obj is None or not self.is_used_by_conduct_records(obj)

    def get_deleted_objects(self, objs, request):
        deleted_objects, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        if any(self.is_used_by_conduct_records(obj) for obj in objs):
            perms_needed.add('已被奖惩记录使用的严重程度系数规则')
        return deleted_objects, model_count, perms_needed, protected


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
        'severity__code',
        'severity__name',
        'reason'
    ]
    readonly_fields = ['recorded_by', 'recorded_at', 'updated_by', 'updated_at', 'reviewed_by', 'reviewed_at']
    date_hierarchy = 'occurred_date'

    class Media:
        js = ('behaviors/js/conduct_record_admin.js',)

    def _can_record(self, request):
        return can_record_conduct(request.user)

    def _can_review(self, request):
        return can_review_conduct(request.user)

    def _can_view_all(self, request):
        return can_view_all_conduct_records(request.user)

    def has_module_permission(self, request):
        return can_access_conduct_record_admin_module(request.user)

    def has_view_permission(self, request, obj=None):
        return can_view_conduct_record_admin(request.user, obj)

    def has_add_permission(self, request):
        return can_record_conduct(request.user)

    def has_change_permission(self, request, obj=None):
        return can_change_conduct_record_admin(request.user, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related(
            'student',
            'item__category',
            'severity',
            'recorded_by',
            'updated_by',
            'reviewed_by',
        )
        return get_conduct_record_admin_queryset(queryset, request.user)

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
        default_rule = get_default_conduct_severity(nature) if nature else None
        default_code = default_rule.severity.code if default_rule is not None else ''
        if nature and choices and not default_code:
            choices.insert(0, {'value': '', 'label': '请选择程度（未配置默认项）'})
        elif nature and not choices:
            choices = [{'value': '', 'label': '当前性质未配置严重程度规则'}]
        return JsonResponse({
            'choices': choices,
            'default': default_code,
        })

    def get_fieldsets(self, request, obj=None):
        basic_fields = self.record_fields
        if obj is not None:
            basic_fields = self.record_fields + ('score_formula_display',)

        fieldsets = [
            ('基本信息', {
                'fields': basic_fields,
                'description': '当前分值 = 事项默认分值 × 严重程度系数。默认程度由对应性质的规则配置决定。',
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
        prepare_conduct_record_for_save(obj, actor=request.user, change=change)
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
