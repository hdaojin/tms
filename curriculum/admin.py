from django import forms
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import CharField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.forms.models import BaseInlineFormSet

from .models import (
    CompetitionType,
    ModuleAxis,
    Project,
    StandardModule,
    StandardModuleAxisMap,
    StandardModuleSet,
)


def format_module_axis_label(module_axis):
    return f'{module_axis.code} - {module_axis.name}'


def get_project_module_axis_queryset(project):
    if project is None:
        return ModuleAxis.objects.none()
    return ModuleAxis.objects.filter(project=project).order_by('sort_order', 'code', 'name')


class HiddenFromAdminIndexMixin:
    def get_model_perms(self, request):
        return {}


class StandardModuleAxisMapAdminForm(forms.ModelForm):
    class Meta:
        model = StandardModuleAxisMap
        fields = '__all__'

    def __init__(self, *args, module=None, **kwargs):
        super().__init__(*args, **kwargs)
        module = module or getattr(self.instance, 'module', None)
        queryset = ModuleAxis.objects.none()
        if module is not None and module.pk:
            queryset = get_project_module_axis_queryset(module.project)
        elif self.instance.pk and self.instance.module_axis_id:
            queryset = ModuleAxis.objects.filter(pk=self.instance.module_axis_id).select_related('project')

        self.fields['module_axis'].queryset = queryset
        self.fields['module_axis'].label_from_instance = format_module_axis_label


class StandardModuleAxisMapInlineFormSet(BaseInlineFormSet):
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['module'] = self.instance
        return kwargs

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        active_forms = [
            form
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
        ]
        if not active_forms:
            return

        primary_forms = [form for form in active_forms if form.cleaned_data.get('is_primary')]
        if len(primary_forms) > 1:
            raise ValidationError('同一标准模块只能设置一个主能力主线映射。')
        if len(primary_forms) == 0:
            raise ValidationError('请至少选择一条主能力主线映射。')


@admin.register(CompetitionType)
class CompetitionTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'level', 'weight', 'created_at')
    list_filter = ('level',)
    search_fields = ('name', 'code')
    ordering = ('level', 'name')


class StandardModuleSetInline(admin.TabularInline):
    model = StandardModuleSet
    extra = 0
    fields = ('code', 'name', 'sort_order', 'is_current')
    show_change_link = True
    ordering = ('-is_current', 'sort_order', 'name')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'competition_type_display', 'current_standard_module_set_display', 'created_at')
    list_filter = ('competition_type',)
    search_fields = ('name', 'code', 'competition_type__name', 'competition_type__code')
    autocomplete_fields = ['competition_type']
    inlines = [StandardModuleSetInline]

    def get_queryset(self, request):
        competition_type_name_subquery = CompetitionType.objects.filter(
            pk=OuterRef('competition_type_id')
        ).values('name')[:1]
        return super().get_queryset(request).annotate(
            competition_type_name_for_admin=Coalesce(
                Subquery(competition_type_name_subquery),
                Value('', output_field=CharField()),
            )
        ).order_by('competition_type_name_for_admin', 'name', 'code')

    @admin.display(description='所属赛事类型', ordering='competition_type_name_for_admin')
    def competition_type_display(self, obj):
        if getattr(obj, 'competition_type_name_for_admin', ''):
            return obj.competition_type_name_for_admin
        try:
            return obj.competition_type.name
        except ObjectDoesNotExist:
            if obj.competition_type_id:
                return f'缺失赛事类型（ID: {obj.competition_type_id}）'
            return '未分配赛事类型'

    @admin.display(description='当前标准模块版本')
    def current_standard_module_set_display(self, obj):
        return obj.current_standard_module_set or '-'


@admin.register(ModuleAxis)
class ModuleAxisAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'project', 'is_active', 'sort_order')
    list_filter = ('project__competition_type', 'project', 'is_active')
    search_fields = ('name', 'code', 'project__name')
    autocomplete_fields = ['project']
    list_select_related = ('project',)
    ordering = ('project__name', 'sort_order', 'code', 'name')


@admin.register(StandardModuleSet)
class StandardModuleSetAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    search_fields = ('name', 'code', 'project__name')
    list_display = ('name', 'code', 'project', 'is_current', 'sort_order')
    list_filter = ('project__competition_type', 'project', 'is_current')
    autocomplete_fields = ['project']
    list_select_related = ('project',)
    ordering = ('project__name', '-is_current', 'sort_order', 'name')


class StandardModuleAxisMapInline(admin.TabularInline):
    model = StandardModuleAxisMap
    form = StandardModuleAxisMapAdminForm
    formset = StandardModuleAxisMapInlineFormSet
    extra = 1
    fields = ('module_axis', 'is_primary', 'weight', 'note')
    verbose_name = '能力主线映射'
    verbose_name_plural = '能力主线映射（若已配置，需确保一条且仅一条主映射）'


@admin.register(StandardModule)
class StandardModuleAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code', 'project__name', 'module_set__name')
    list_display = ('name', 'code', 'project', 'module_set', 'default_counts_towards_ranking', 'sort_order', 'is_current_module')
    list_filter = ('project__competition_type', 'project', 'module_set', 'module_set__is_current', 'default_counts_towards_ranking')
    autocomplete_fields = ['project', 'module_set']
    list_select_related = ('project', 'module_set')
    ordering = ('project__name', '-module_set__is_current', 'module_set__sort_order', 'sort_order', 'code', 'name')
    inlines = [StandardModuleAxisMapInline]

    @admin.display(description='当前版本')
    def is_current_module(self, obj):
        return obj.is_current


@admin.register(StandardModuleAxisMap)
class StandardModuleAxisMapAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    search_fields = ('module__code', 'module__name', 'module_axis__code', 'module_axis__name')
    list_display = ('module', 'module_axis', 'is_primary', 'weight')
    list_filter = ('is_primary', 'module__project', 'module_axis')
    autocomplete_fields = ['module', 'module_axis']
