from django.contrib import admin
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Max

from competitions.models import StandardModule
from core.constants import GROUP_COACH

from .models import Assessment, Score, AssessmentModule, AssessmentAttachment


User = get_user_model()


def get_current_module_queryset():
    return StandardModule.objects.current().select_related('project', 'module_set').order_by(
        'project__name',
        'module_set__sort_order',
        'sort_order',
        'code',
        'name',
    )


class AssessmentModuleInline(admin.TabularInline):
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
        'is_locked',
        'is_material_locked',
    )
    readonly_fields = ('is_locked', 'is_material_locked')

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        next_sort_order = 0
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

            @property
            def empty_form(self):
                form = super().empty_form
                if 'sort_order' in form.fields and form.initial.get('sort_order') in (None, ''):
                    form.fields['sort_order'].initial = next_sort_order
                    form.initial['sort_order'] = next_sort_order
                return form

        return PrefilledAssessmentModuleInlineFormSet

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "responsible_coach":
            kwargs["queryset"] = User.objects.filter(groups__name=GROUP_COACH).order_by(
                "last_name", "first_name", "username"
            )
        elif db_field.name == "module":
            kwargs["queryset"] = get_current_module_queryset()

        form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if form_field and db_field.name == "responsible_coach":
            form_field.label_from_instance = lambda obj: obj.full_info  # type: ignore
        return form_field

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
    list_display = ('name', 'start_date', 'end_date', 'created_at', 'updated_at')
    search_fields = ('name',)
    list_filter = ('start_date', 'end_date')
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
    list_display = (
        'assessment',
        'sort_order',
        'module',
        'responsible_coach',
        'max_score',
        'is_locked',
        'is_material_locked',
    )
    list_display_links = ('assessment', 'module')
    list_editable = ('sort_order',)
    list_filter = ('assessment', 'responsible_coach', 'is_locked', 'is_material_locked')
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
            kwargs["queryset"] = get_current_module_queryset()

        form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if form_field and db_field.name == "responsible_coach":
            form_field.label_from_instance = lambda obj: obj.full_info  # type: ignore
        return form_field
    
    def get_form(self, request, obj=None, **kwargs):   # type: ignore
        # 保存 obj 到 request 中，以便在 Inline 中使用
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)



