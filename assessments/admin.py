from django.contrib import admin
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Max
from django.http import JsonResponse
from django.urls import path, reverse

from curriculum.models import StandardModule
from core.constants import GROUP_COACH

from .models import Assessment, Score, AssessmentModule, AssessmentAttachment


User = get_user_model()


ASSESSMENT_MODULE_RANKING_HELP_TEXT = (
    '选择标准模块后会显示该标准模块的默认排名规则；未手动修改时会自动同步，'
    '如需例外可再手动调整。'
)


def get_current_module_queryset():
    return StandardModule.objects.current().select_related('project', 'module_set').order_by(
        'project__name',
        'module_set__sort_order',
        'sort_order',
        'code',
        'name',
    )


def get_training_cycle_module_queryset(training_cycle):
    if training_cycle is None:
        return StandardModule.objects.none()
    return (
        StandardModule.objects.filter(module_set=training_cycle.module_set)
        .select_related('project', 'module_set')
        .order_by('sort_order', 'code', 'name')
    )


class AssessmentModuleInline(admin.TabularInline):
    form = None
    model = AssessmentModule
    extra = 0
    autocomplete_fields = ['module']
    ordering = ('sort_order', 'id')
    fields = (
        'sort_order',
        'module',
        'responsible_coach',
        'max_score',
        'duration',
        'counts_towards_ranking',
        'is_locked',
        'is_material_locked',
    )
    readonly_fields = ('is_locked', 'is_material_locked')

    class Media:
        js = ('assessments/js/assessment_module_admin.js',)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.ranking_default_url = reverse(
            'admin:assessments_assessmentmodule_module_ranking_default'
        )
        next_sort_order = 0
        module_queryset = get_training_cycle_module_queryset(obj.training_cycle if obj else None)
        if obj and obj.pk:
            max_sort_order = obj.assessmentmodule_set.aggregate(
                max_sort_order=Max('sort_order')
            )['max_sort_order']
            if max_sort_order is not None:
                next_sort_order = max_sort_order + 1

        class PrefilledAssessmentModuleInlineFormSet(formset):
            def __init__(self, *args, **inner_kwargs):
                super().__init__(*args, **inner_kwargs)
                for index, form in enumerate(self.extra_forms):
                    if 'sort_order' in form.fields and form.initial.get('sort_order') in (None, ''):
                        initial_value = next_sort_order + index
                        form.fields['sort_order'].initial = initial_value
                        form.initial['sort_order'] = initial_value
                    if 'module' in form.fields:
                        form.fields['module'].queryset = module_queryset
                for form in self.initial_forms:
                    if 'module' in form.fields:
                        form.fields['module'].queryset = module_queryset

            @property
            def empty_form(self):
                form = super().empty_form
                if 'sort_order' in form.fields and form.initial.get('sort_order') in (None, ''):
                    form.fields['sort_order'].initial = next_sort_order
                    form.initial['sort_order'] = next_sort_order
                if 'module' in form.fields:
                    form.fields['module'].queryset = module_queryset
                return form

        return PrefilledAssessmentModuleInlineFormSet

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "responsible_coach":
            kwargs["queryset"] = User.objects.filter(groups__name=GROUP_COACH).order_by(
                "last_name", "first_name", "username"
            )
        elif db_field.name == "module":
            kwargs["queryset"] = StandardModule.objects.none()

        form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if form_field and db_field.name == "responsible_coach":
            form_field.label_from_instance = lambda obj: obj.full_info  # type: ignore
        return form_field


class AssessmentModuleAdminForm(forms.ModelForm):
    ranking_default_url = ''

    class Meta:
        model = AssessmentModule
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        module_field = self.fields.get('module')
        counts_field = self.fields.get('counts_towards_ranking')

        if module_field and self.ranking_default_url:
            module_field.widget.attrs['data-ranking-default-url'] = self.ranking_default_url

        if counts_field:
            counts_field.help_text = ASSESSMENT_MODULE_RANKING_HELP_TEXT
            counts_field.widget.attrs['data-follow-module-default'] = (
                'true' if self.should_follow_module_default() else 'false'
            )
            counts_field.widget.attrs['data-ranking-default-help'] = (
                ASSESSMENT_MODULE_RANKING_HELP_TEXT
            )

    def should_follow_module_default(self):
        return not self.instance.pk and not self.is_bound

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk and 'counts_towards_ranking' in self.changed_data:
            self.instance._counts_towards_ranking_explicit = True
        return cleaned_data

class AssessmentAttachmentInline(admin.TabularInline):
    """附件内联编辑"""
    model = AssessmentAttachment
    extra = 1
    verbose_name = '试题附件'
    verbose_name_plural = '试题附件'
    fields = ['file', 'description', 'uploaded_at']
    readonly_fields = ['uploaded_at']

class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 为 participants 字段设置 label_from_instance
        participants_field = self.fields.get('participants')
        if participants_field:
            participants_field.label_from_instance = lambda obj: obj.full_info # type: ignore

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    form = AssessmentForm
    list_display = ('name', 'training_cycle', 'start_date', 'end_date', 'created_at', 'updated_at')
    search_fields = ('name', 'training_cycle__name', 'training_cycle__code')
    list_filter = ('training_cycle', 'start_date', 'end_date')
    autocomplete_fields = ['training_cycle']
    list_select_related = ('training_cycle',)
    filter_horizontal = ('participants',)
    inlines = [AssessmentModuleInline]
    date_hierarchy = 'start_date'

class ScoreInline(admin.TabularInline):
    model = Score
    extra = 0
    # autocomplete_fields = ['user'] # 如果用户很多，可以开启这个
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # 尝试限制用户选择范围为本次考核的参与人员
        if db_field.name == "user":
            parent_obj = getattr(request, '_obj_', None)
            if parent_obj and hasattr(parent_obj, 'assessment'): 
                 kwargs["queryset"] = parent_obj.assessment.participants.all()
            
            form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
            if form_field:
                 form_field.label_from_instance = lambda obj: obj.full_info # type: ignore
            return form_field
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(AssessmentModule)
class AssessmentModuleAdmin(admin.ModelAdmin):
    form = AssessmentModuleAdminForm
    list_display = (
        'assessment',
        'sort_order',
        'module',
        'responsible_coach',
        'max_score',
        'counts_towards_ranking',
        'is_locked',
        'is_material_locked',
    )
    list_display_links = ('assessment', 'module')
    list_editable = ('sort_order',)
    list_filter = ('assessment', 'responsible_coach', 'counts_towards_ranking', 'is_locked', 'is_material_locked')
    search_fields = ('assessment__name', 'module__name')
    readonly_fields = (
        'locked_at',
        'locked_by',
        'material_locked_at',
        'material_locked_by',
    )
    fields = (
        'assessment',
        'module',
        'responsible_coach',
        'sort_order',
        'max_score',
        'duration',
        'counts_towards_ranking',
        'is_locked',
        'locked_at',
        'locked_by',
        'is_material_locked',
        'material_locked_at',
        'material_locked_by',
        'question_file',
        'scoring_standard_file',
        'scoring_sheet_file',
        'scoring_script_file',
    )
    inlines = [AssessmentAttachmentInline, ScoreInline]
    ordering = ('assessment', 'sort_order', 'module__code', 'pk')

    class Media:
        js = ('assessments/js/assessment_module_admin.js',)

    def get_urls(self):
        return [
            path(
                'module-ranking-default/',
                self.admin_site.admin_view(self.module_ranking_default_view),
                name='assessments_assessmentmodule_module_ranking_default',
            ),
        ] + super().get_urls()

    def module_ranking_default_view(self, request):
        module_id = request.GET.get('module_id')
        if not module_id:
            return JsonResponse({'found': False})

        module = StandardModule.objects.filter(pk=module_id).only(
            'pk',
            'code',
            'name',
            'default_counts_towards_ranking',
        ).first()
        if module is None:
            return JsonResponse({'found': False})

        return JsonResponse(
            {
                'found': True,
                'module': {
                    'id': module.pk,
                    'label': str(module),
                    'default_counts_towards_ranking': module.default_counts_towards_ranking,
                },
            }
        )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        assessment_id = request.GET.get('assessment')
        if not assessment_id:
            return initial

        try:
            assessment_id = int(assessment_id)
        except (TypeError, ValueError):
            return initial

        max_sort_order = AssessmentModule.objects.filter(
            assessment_id=assessment_id
        ).aggregate(max_sort_order=Max('sort_order'))['max_sort_order']
        initial['assessment'] = assessment_id
        initial['sort_order'] = (max_sort_order + 1) if max_sort_order is not None else 0
        return initial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "responsible_coach":
            kwargs["queryset"] = User.objects.filter(groups__name=GROUP_COACH).order_by(
                "last_name", "first_name", "username"
            )
        elif db_field.name == "module":
            assessment = None
            assessment_id = request.GET.get('assessment') or request.POST.get('assessment')
            if getattr(request, '_obj_', None) is not None:
                assessment = request._obj_.assessment
            elif assessment_id:
                assessment = Assessment.objects.filter(pk=assessment_id).select_related('training_cycle__module_set').first()
            kwargs["queryset"] = get_training_cycle_module_queryset(assessment.training_cycle if assessment else None)

        form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if form_field and db_field.name == "responsible_coach":
            form_field.label_from_instance = lambda obj: obj.full_info  # type: ignore
        return form_field
    
    def get_form(self, request, obj=None, **kwargs):   # type: ignore
        # 保存 obj 到 request 中，以便在 Inline 中使用
        request._obj_ = obj
        form = super().get_form(request, obj, **kwargs)
        form.ranking_default_url = reverse(
            'admin:assessments_assessmentmodule_module_ranking_default'
        )
        return form


AssessmentModuleInline.form = AssessmentModuleAdminForm



