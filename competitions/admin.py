from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.forms.models import BaseInlineFormSet

from .models import (
    Competition,
    CompetitionModule,
    CompetitionModuleMapping,
    CompetitionProject,
    CompetitionResult,
    CompetitionType,
    Competitor,
    CompetitorUser,
    Expert,
    Member,
    Module,
    ModuleSet,
    Project,
    SkillPosition,
)


def format_standard_module_label(module):
    return f'{module.code} - {module.name} [{module.module_set.name}]'


def format_member_label(member):
    return f'{member.name} [{member.get_level_display()}]'


def get_project_module_queryset(project):
    if project is None:
        return Module.objects.none()
    return Module.objects.filter(project=project).select_related('project', 'module_set').order_by(
        '-module_set__is_current',
        'module_set__sort_order',
        'sort_order',
        'code',
        'name',
    )


def get_member_queryset_for_competition_project(competition_project):
    queryset = Member.objects.order_by('level', 'name')
    if competition_project is None:
        return queryset
    return queryset.filter(level=competition_project.required_member_level)


class HiddenFromAdminIndexMixin:
    def get_model_perms(self, request):
        return {}


class CompetitionModuleMappingAdminForm(forms.ModelForm):
    class Meta:
        model = CompetitionModuleMapping
        fields = '__all__'

    def __init__(self, *args, competition_module=None, **kwargs):
        super().__init__(*args, **kwargs)
        competition_module = competition_module or getattr(self.instance, 'competition_module', None)
        queryset = Module.objects.none()
        if competition_module is not None and competition_module.pk:
            queryset = get_project_module_queryset(competition_module.project)
        elif self.instance.pk and self.instance.module_id:
            queryset = Module.objects.filter(pk=self.instance.module_id).select_related('project', 'module_set')

        self.fields['module'].queryset = queryset
        self.fields['module'].label_from_instance = format_standard_module_label


class CompetitionModuleMappingInlineFormSet(BaseInlineFormSet):
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['competition_module'] = self.instance
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
            raise ValidationError('同一官方模块只能设置一个主映射。')
        if len(primary_forms) == 0:
            raise ValidationError('请至少选择一条主映射。')


class CompetitionProjectScopedMemberFormMixin:
    def __init__(self, *args, competition_project=None, **kwargs):
        self._competition_project = competition_project
        super().__init__(*args, **kwargs)

        if 'member' not in self.fields:
            return

        competition_project = self.get_competition_project()
        self.fields['member'].queryset = get_member_queryset_for_competition_project(competition_project)
        self.fields['member'].label_from_instance = format_member_label
        if competition_project is None:
            self.fields['member'].help_text = '请先选择具体赛项，再选择匹配层级的代表队。'
        else:
            self.fields['member'].help_text = (
                f'当前赛事级别要求选择“{competition_project.required_member_level_label}”代表队。'
            )

    def get_competition_project(self):
        if self._competition_project is not None:
            return self._competition_project

        competition_project_id = self.data.get(self.add_prefix('competition_project'))
        if competition_project_id:
            return CompetitionProject.objects.select_related('competition__competition_type').filter(
                pk=competition_project_id,
            ).first()

        if getattr(self.instance, 'competition_project_id', None):
            return self.instance.competition_project
        return None


class CompetitorAdminForm(CompetitionProjectScopedMemberFormMixin, forms.ModelForm):
    class Meta:
        model = Competitor
        fields = '__all__'


class ExpertAdminForm(CompetitionProjectScopedMemberFormMixin, forms.ModelForm):
    class Meta:
        model = Expert
        fields = '__all__'


class CompetitionProjectScopedMemberInlineFormSet(BaseInlineFormSet):
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['competition_project'] = self.instance
        return kwargs


@admin.register(CompetitionType)
class CompetitionTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'level', 'weight', 'created_at')
    list_filter = ('level',)
    search_fields = ('name', 'code')
    ordering = ('level', 'name')


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'competition_type', 'start_date', 'location', 'competition_project_total')
    list_filter = ('competition_type', 'start_date')
    search_fields = ('name', 'code')
    autocomplete_fields = ['competition_type']
    list_select_related = ('competition_type',)
    date_hierarchy = 'start_date'
    ordering = ('-start_date', 'name')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('competition_type').annotate(
            competition_project_total=Count('competition_projects', distinct=True),
        )

    @admin.display(description='赛项数', ordering='competition_project_total')
    def competition_project_total(self, obj):
        return obj.competition_project_total


class ModuleSetInline(admin.TabularInline):
    model = ModuleSet
    extra = 0
    fields = ('code', 'name', 'sort_order', 'is_current')
    show_change_link = True
    ordering = ('-is_current', 'sort_order', 'name')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'competition_type', 'current_module_set_display', 'created_at')
    list_filter = ('competition_type',)
    search_fields = ('name', 'code', 'competition_type__name')
    autocomplete_fields = ['competition_type']
    list_select_related = ('competition_type',)
    ordering = ('name',)
    inlines = [ModuleSetInline]

    @admin.display(description='当前模块集')
    def current_module_set_display(self, obj):
        return obj.current_module_set or '-'


class CompetitionModuleInline(admin.TabularInline):
    model = CompetitionModule
    extra = 0
    fields = ('sort_order', 'code', 'name')
    ordering = ('sort_order', 'code', 'pk')
    show_change_link = True
    verbose_name = '官方模块'
    verbose_name_plural = '本届官方模块（保存后进入详情页维护标准模块映射）'


class CompetitorInline(admin.TabularInline):
    model = Competitor
    form = CompetitorAdminForm
    formset = CompetitionProjectScopedMemberInlineFormSet
    extra = 0
    fields = ('name', 'member', 'organization', 'gender', 'user')
    autocomplete_fields = ['user']
    ordering = ('name',)
    show_change_link = True
    verbose_name = '选手'
    verbose_name_plural = '选手'


class ExpertInline(admin.TabularInline):
    model = Expert
    form = ExpertAdminForm
    formset = CompetitionProjectScopedMemberInlineFormSet
    extra = 0
    fields = ('name', 'member', 'organization', 'user')
    autocomplete_fields = ['user']
    ordering = ('name',)
    show_change_link = True
    verbose_name = '专家'
    verbose_name_plural = '专家'


class SkillPositionInline(admin.TabularInline):
    model = SkillPosition
    extra = 0
    fields = ('name', 'position_name', 'organization', 'user')
    autocomplete_fields = ['user']
    ordering = ('position_name', 'name')
    show_change_link = True
    verbose_name = '岗位人员'
    verbose_name_plural = '岗位人员'


@admin.register(CompetitionProject)
class CompetitionProjectAdmin(admin.ModelAdmin):
    list_display = (
        'competition',
        'project',
        'member_scope_display',
        'official_module_total',
        'competitor_total',
        'result_total',
    )
    list_filter = ('competition', 'project')
    search_fields = ('competition__name', 'competition__code', 'project__name', 'project__code')
    autocomplete_fields = ['competition', 'project']
    list_select_related = ('competition__competition_type', 'project')
    ordering = ('-competition__start_date', 'competition__name', 'project__name')
    fields = ('competition', 'project', 'document', 'description')
    inlines = [CompetitionModuleInline, CompetitorInline, ExpertInline, SkillPositionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('competition__competition_type', 'project').annotate(
            official_module_total=Count('competition_modules', distinct=True),
            competitor_total=Count('competitors', distinct=True),
            result_total=Count('competitors__results', distinct=True),
        )

    @admin.display(description='代表队层级', ordering='competition__competition_type__level')
    def member_scope_display(self, obj):
        return obj.required_member_level_label

    @admin.display(description='官方模块数', ordering='official_module_total')
    def official_module_total(self, obj):
        return obj.official_module_total

    @admin.display(description='选手数', ordering='competitor_total')
    def competitor_total(self, obj):
        return obj.competitor_total

    @admin.display(description='成绩数', ordering='result_total')
    def result_total(self, obj):
        return obj.result_total


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'level', 'flag')
    list_filter = ('level',)
    search_fields = ('name', 'code')
    ordering = ('level', 'name')


@admin.register(CompetitionResult)
class CompetitionResultAdmin(admin.ModelAdmin):
    list_display = (
        'competitor',
        'competition_project_display',
        'member_display',
        'score_700',
        'rank',
        'medal',
    )
    list_filter = (
        'medal',
        'competitor__competition_project__competition',
        'competitor__competition_project__project',
        'competitor__member',
    )
    search_fields = ('competitor__name', 'competitor__organization', 'competitor__user__username')
    autocomplete_fields = ['competitor']
    list_select_related = (
        'competitor__competition_project__competition',
        'competitor__competition_project__project',
        'competitor__member',
        'competitor__user',
    )
    ordering = (
        'competitor__competition_project__competition__name',
        'competitor__competition_project__project__name',
        'rank',
        '-score_700',
    )
    fields = ('competitor', 'score_100', 'score_700', 'rank', 'medal')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'competitor__competition_project__competition',
            'competitor__competition_project__project',
            'competitor__member',
            'competitor__user',
        )

    @admin.display(description='具体赛项')
    def competition_project_display(self, obj):
        return obj.competitor.competition_project

    @admin.display(description='代表队')
    def member_display(self, obj):
        return obj.competitor.member


@admin.register(ModuleSet)
class ModuleSetAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    search_fields = ('name', 'code', 'project__name')
    list_display = ('name', 'code', 'project', 'is_current', 'sort_order')
    list_filter = ('project', 'is_current')
    autocomplete_fields = ['project']
    list_select_related = ('project',)
    ordering = ('project__name', '-is_current', 'sort_order', 'name')


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code', 'project__name', 'module_set__name')
    list_display = ('name', 'code', 'project', 'module_set', 'sort_order', 'is_current_module')
    list_filter = ('project', 'module_set', 'module_set__is_current')
    autocomplete_fields = ['project', 'module_set']
    list_select_related = ('project', 'module_set')
    ordering = ('project__name', '-module_set__is_current', 'module_set__sort_order', 'sort_order', 'code', 'name')

    @admin.display(description='当前模块')
    def is_current_module(self, obj):
        return obj.is_current


class CompetitionModuleMappingInline(admin.TabularInline):
    model = CompetitionModuleMapping
    form = CompetitionModuleMappingAdminForm
    formset = CompetitionModuleMappingInlineFormSet
    extra = 1
    fields = ('module', 'is_primary', 'weight', 'note')
    verbose_name = '标准模块映射'
    verbose_name_plural = '标准模块映射（请确保一条且仅一条主映射）'


@admin.register(CompetitionModule)
class CompetitionModuleAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    search_fields = (
        'code',
        'name',
        'competition_project__competition__name',
        'competition_project__project__name',
        'module_mappings__module__name',
        'module_mappings__module__code',
    )
    list_display = ('code', 'name', 'competition_project', 'primary_module_display', 'mapped_modules_display', 'sort_order')
    list_filter = ('competition_project__competition', 'competition_project__project')
    autocomplete_fields = ['competition_project']
    list_select_related = ('competition_project__competition', 'competition_project__project')
    ordering = (
        'competition_project__competition__name',
        'competition_project__project__name',
        'sort_order',
        'code',
    )
    fields = ('competition_project', 'sort_order', 'code', 'name', 'description')
    inlines = [CompetitionModuleMappingInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'competition_project__competition',
            'competition_project__project',
        ).prefetch_related('module_mappings__module__module_set')

    @admin.display(description='主映射标准模块')
    def primary_module_display(self, obj):
        primary_module = obj.primary_module
        if primary_module is None:
            return '-'
        return format_standard_module_label(primary_module)

    @admin.display(description='全部映射')
    def mapped_modules_display(self, obj):
        labels = []
        for mapping in obj.module_mappings.all():
            label = format_standard_module_label(mapping.module)
            if mapping.is_primary:
                label = f'★ {label}'
            labels.append(label)
        return '，'.join(labels) or '-'


@admin.register(CompetitionModuleMapping)
class CompetitionModuleMappingAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    search_fields = (
        'competition_module__code',
        'competition_module__name',
        'module__code',
        'module__name',
    )
    list_display = ('competition_module', 'module', 'is_primary', 'weight')
    list_filter = ('is_primary', 'module__project', 'module__module_set')
    autocomplete_fields = ['competition_module']


@admin.register(CompetitorUser)
class CompetitorUserAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    search_fields = ('username', 'first_name')
    list_display = ('username', 'first_name', 'email')


@admin.register(Competitor)
class CompetitorAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    form = CompetitorAdminForm
    list_display = ('name', 'gender', 'member', 'organization', 'competition_project', 'user', 'created_at')
    list_filter = ('member', 'gender', 'competition_project__competition')
    search_fields = ('name', 'member__name', 'user__username', 'competition_project__project__name', 'organization')
    autocomplete_fields = ['user', 'competition_project']
    list_select_related = ('member', 'competition_project__competition', 'competition_project__project', 'user')


@admin.register(SkillPosition)
class SkillPositionAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    list_display = ('name', 'position_name', 'competition_project', 'organization', 'user')
    list_filter = ('competition_project', 'position_name')
    search_fields = ('name', 'position_name', 'user__username', 'organization')
    autocomplete_fields = ['user', 'competition_project']
    list_select_related = ('competition_project__competition', 'competition_project__project', 'user')


@admin.register(Expert)
class ExpertAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    form = ExpertAdminForm
    list_display = ('name', 'user', 'member', 'competition_project', 'organization')
    list_filter = ('member', 'competition_project')
    search_fields = ('name', 'user__username', 'member__name', 'organization')
    autocomplete_fields = ['user', 'competition_project']
    list_select_related = ('member', 'competition_project__competition', 'competition_project__project', 'user')

