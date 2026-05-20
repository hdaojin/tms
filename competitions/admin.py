from django import forms
from django.contrib import admin
from django.db.models import Count
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django.utils.html import format_html
from urllib.parse import urlencode

from curriculum.models import ModuleAxis, StandardModule

from .models import (
    Competition,
    CompetitionModuleAxisMap,
    CompetitionModule,
    CompetitionModuleStandardModuleMap,
    CompetitionPerson,
    CompetitionProject,
    CompetitionProjectMember,
    CompetitionResult,
    Competitor,
    CompetitorUser,
    Expert,
    Member,
    SkillPosition,
)
from .selectors import (
    format_competition_person_label,
    format_member_label,
    format_module_axis_label,
    format_standard_module_label,
    get_available_members_for_competition_project,
    get_competition_person_queryset,
    get_competition_project_queryset,
    get_members_for_competition_project,
    get_project_module_axis_queryset,
    get_project_module_queryset,
)
from .validators import validate_primary_inline_forms


def format_competition_module_mappings(competition_module):
    labels = []
    for mapping in competition_module.module_mappings.all():
        label = format_standard_module_label(mapping.module)
        if mapping.is_primary:
            label = f'★ {label}'
        labels.append(label)
    return '，'.join(labels) or '-'


def format_competition_module_axis_mappings(competition_module):
    labels = []
    for mapping in competition_module.axis_mappings.all():
        label = format_module_axis_label(mapping.module_axis)
        if mapping.is_primary:
            label = f'★ {label}'
        labels.append(label)
    return '，'.join(labels) or '-'


class HiddenFromAdminIndexMixin:
    def get_model_perms(self, request):
        return {}


class CompetitionModuleStandardModuleMapAdminForm(forms.ModelForm):
    class Meta:
        model = CompetitionModuleStandardModuleMap
        fields = '__all__'

    def __init__(self, *args, competition_module=None, **kwargs):
        super().__init__(*args, **kwargs)
        competition_module = competition_module or getattr(self.instance, 'competition_module', None)
        queryset = StandardModule.objects.none()
        if competition_module is not None and competition_module.pk:
            queryset = get_project_module_queryset(competition_module.project)
        elif self.instance.pk and self.instance.module_id:
            queryset = StandardModule.objects.filter(pk=self.instance.module_id).select_related('project', 'module_set')

        self.fields['module'].queryset = queryset
        self.fields['module'].label_from_instance = format_standard_module_label


class BaseCompetitionModuleMappingInlineFormSet(BaseInlineFormSet):
    duplicate_primary_message = ''
    missing_primary_message = ''

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['competition_module'] = self.instance
        return kwargs

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        validate_primary_inline_forms(
            self.forms,
            duplicate_message=self.duplicate_primary_message,
            missing_message=self.missing_primary_message,
        )


class CompetitionModuleStandardModuleMapInlineFormSet(BaseCompetitionModuleMappingInlineFormSet):
    duplicate_primary_message = '同一官方模块只能设置一个主映射。'
    missing_primary_message = '请至少选择一条主映射。'


class CompetitionModuleAxisMapAdminForm(forms.ModelForm):
    class Meta:
        model = CompetitionModuleAxisMap
        fields = '__all__'

    def __init__(self, *args, competition_module=None, **kwargs):
        super().__init__(*args, **kwargs)
        competition_module = competition_module or getattr(self.instance, 'competition_module', None)
        queryset = ModuleAxis.objects.none()
        if competition_module is not None and competition_module.pk:
            queryset = get_project_module_axis_queryset(competition_module.project)
        elif self.instance.pk and self.instance.module_axis_id:
            queryset = ModuleAxis.objects.filter(pk=self.instance.module_axis_id).select_related('project')

        self.fields['module_axis'].queryset = queryset
        self.fields['module_axis'].label_from_instance = format_module_axis_label


class CompetitionModuleAxisMapInlineFormSet(BaseCompetitionModuleMappingInlineFormSet):
    duplicate_primary_message = '同一官方模块只能设置一个主主线映射。'
    missing_primary_message = '请至少选择一条主主线映射。'


class CompetitionProjectAdminFormMixin:
    resolve_competition_project_from_data = False

    def __init__(self, *args, competition_project=None, **kwargs):
        self._competition_project = competition_project
        super().__init__(*args, **kwargs)

    def get_competition_project_queryset(self):
        return get_competition_project_queryset()

    def get_competition_project(self):
        if self._competition_project is not None:
            return self._competition_project

        if self.resolve_competition_project_from_data:
            competition_project_id = self.data.get(self.add_prefix('competition_project'))
            if competition_project_id:
                return self.get_competition_project_queryset().filter(pk=competition_project_id).first()

        if getattr(self.instance, 'competition_project_id', None):
            return self.instance.competition_project
        return None


class CompetitionProjectScopedMemberFormMixin(CompetitionProjectAdminFormMixin):
    resolve_competition_project_from_data = True

    def __init__(self, *args, competition_project=None, **kwargs):
        super().__init__(*args, competition_project=competition_project, **kwargs)

        if 'person' in self.fields:
            self.fields['person'].queryset = get_competition_person_queryset()
            self.fields['person'].label_from_instance = format_competition_person_label

        if 'member' not in self.fields:
            return

        competition_project = self.get_competition_project()
        current_member = getattr(self.instance, 'member', None)
        self.fields['member'].queryset = get_members_for_competition_project(
            competition_project,
            include_member=current_member,
        )
        self.fields['member'].label_from_instance = format_member_label
        if competition_project is None or competition_project.required_member_level is None:
            self.fields['member'].help_text = '请先选择具体赛项，再选择匹配层级的代表队。'
        else:
            self.fields['member'].help_text = (
                f'当前赛事级别要求选择“{competition_project.required_member_level_label}”代表队。'
                '请先在当前赛项中关联代表队，再为选手或专家选择。'
            )


class CompetitorAdminForm(CompetitionProjectScopedMemberFormMixin, forms.ModelForm):
    class Meta:
        model = Competitor
        fields = '__all__'


class ExpertAdminForm(CompetitionProjectScopedMemberFormMixin, forms.ModelForm):
    class Meta:
        model = Expert
        fields = '__all__'


class CompetitionProjectMemberAdminForm(CompetitionProjectAdminFormMixin, forms.ModelForm):
    class Meta:
        model = CompetitionProjectMember
        fields = '__all__'

    def __init__(self, *args, competition_project=None, **kwargs):
        super().__init__(*args, competition_project=competition_project, **kwargs)
        competition_project = self.get_competition_project()
        current_member = getattr(self.instance, 'member', None)
        self.fields['member'].queryset = get_available_members_for_competition_project(
            competition_project,
            include_member=current_member,
        )
        self.fields['member'].label_from_instance = format_member_label
        if competition_project is None or competition_project.required_member_level is None:
            self.fields['member'].help_text = '请先选择具体赛项，再选择匹配层级的代表队。'
        else:
            self.fields['member'].help_text = (
                f'当前赛事级别要求选择“{competition_project.required_member_level_label}”代表队。'
                '这里仅显示尚未关联到当前赛项的代表队。'
            )


class SkillPositionAdminForm(forms.ModelForm):
    class Meta:
        model = SkillPosition
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'person' in self.fields:
            self.fields['person'].queryset = get_competition_person_queryset()
            self.fields['person'].label_from_instance = format_competition_person_label


class CompetitionProjectScopedMemberInlineFormSet(BaseInlineFormSet):
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['competition_project'] = self.instance
        return kwargs


class CompetitionProjectMemberInline(admin.TabularInline):
    model = CompetitionProjectMember
    form = CompetitionProjectMemberAdminForm
    formset = CompetitionProjectScopedMemberInlineFormSet
    extra = 0
    fields = ('member',)
    ordering = ('member__level', 'member__name')
    show_change_link = True
    verbose_name = '已关联代表队'
    verbose_name_plural = '已关联代表队'


 



class CompetitionProjectInline(admin.TabularInline):
    model = CompetitionProject
    extra = 0
    fields = ('project', 'document', 'description')
    autocomplete_fields = ['project']
    ordering = ('project__name',)
    show_change_link = True
    verbose_name = '具体赛项'
    verbose_name_plural = '具体赛项'


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'competition_type', 'start_date', 'location', 'competition_project_total')
    list_filter = ('competition_type', 'start_date')
    search_fields = ('name', 'code')
    autocomplete_fields = ['competition_type']
    list_select_related = ('competition_type',)
    date_hierarchy = 'start_date'
    ordering = ('-start_date', 'name')
    inlines = [CompetitionProjectInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('competition_type').annotate(
            competition_project_total=Count('competition_projects', distinct=True),
        )

    @admin.display(description='赛项数', ordering='competition_project_total')
    def competition_project_total(self, obj):
        return obj.competition_project_total


@admin.register(CompetitionPerson)
class CompetitionPersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'user', 'created_at')
    search_fields = ('name', 'organization', 'user__username', 'user__first_name', 'user__last_name')
    autocomplete_fields = ['user']
    ordering = ('name', 'organization', 'pk')


class CompetitionModuleInline(admin.TabularInline):
    model = CompetitionModule
    extra = 0
    fields = ('sort_order', 'code', 'name', 'mapped_modules_summary', 'mapped_axes_summary')
    readonly_fields = ('mapped_modules_summary', 'mapped_axes_summary')
    ordering = ('sort_order', 'code', 'pk')
    show_change_link = True
    verbose_name = '官方模块'
    verbose_name_plural = '本届官方模块（可在下方快捷入口或独立“具体赛项模块”后台中集中维护）'

    @admin.display(description='映射关系')
    def mapped_modules_summary(self, obj):
        if obj is None or not obj.pk:
            return '-'
        return format_competition_module_mappings(obj)

    @admin.display(description='主线关系')
    def mapped_axes_summary(self, obj):
        if obj is None or not obj.pk:
            return '-'
        return format_competition_module_axis_mappings(obj)


class CompetitorInline(admin.TabularInline):
    model = Competitor
    form = CompetitorAdminForm
    formset = CompetitionProjectScopedMemberInlineFormSet
    extra = 0
    fields = ('person', 'member', 'gender')
    autocomplete_fields = ['person']
    ordering = ('person__name',)
    show_change_link = True
    verbose_name = '选手'
    verbose_name_plural = '选手'


class ExpertInline(admin.TabularInline):
    model = Expert
    form = ExpertAdminForm
    formset = CompetitionProjectScopedMemberInlineFormSet
    extra = 0
    fields = ('person', 'member')
    autocomplete_fields = ['person']
    ordering = ('person__name',)
    show_change_link = True
    verbose_name = '专家'
    verbose_name_plural = '专家'


class SkillPositionInline(admin.TabularInline):
    model = SkillPosition
    form = SkillPositionAdminForm
    extra = 0
    fields = ('person', 'position_name', 'remarks')
    autocomplete_fields = ['person']
    ordering = ('position_name', 'person__name')
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
        'module_entry_link',
        'competitor_total',
        'result_total',
    )
    list_filter = ('competition', 'project')
    search_fields = ('competition__name', 'competition__code', 'project__name', 'project__code')
    autocomplete_fields = ['competition', 'project']
    list_select_related = ('competition__competition_type', 'project')
    ordering = ('-competition__start_date', 'competition__name', 'project__name')
    fields = ('competition', 'project', 'document', 'description')
    inlines = [CompetitionModuleInline, CompetitionProjectMemberInline, CompetitorInline, ExpertInline, SkillPositionInline]

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if obj is not None:
            fields.insert(2, 'module_entry_link')
        return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly_fields.append('module_entry_link')
        return readonly_fields

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

    @admin.display(description='模块入口')
    def module_entry_link(self, obj):
        module_total = getattr(obj, 'official_module_total', obj.competition_modules.count())
        url = '{}?{}'.format(
            reverse('admin:competitions_competitionmodule_changelist'),
            urlencode({'competition_project__id__exact': obj.pk}),
        )
        return format_html(
            '<a href="{}">进入具体赛项模块（{}）</a>',
            url,
            module_total,
        )

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
    search_fields = ('competitor__person__name', 'competitor__person__organization', 'competitor__person__user__username')
    autocomplete_fields = ['competitor']
    list_select_related = (
        'competitor__competition_project__competition',
        'competitor__competition_project__project',
        'competitor__member',
        'competitor__person__user',
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
            'competitor__person__user',
        )

    @admin.display(description='具体赛项')
    def competition_project_display(self, obj):
        return obj.competitor.competition_project

    @admin.display(description='代表队')
    def member_display(self, obj):
        return obj.competitor.member


class CompetitionModuleStandardModuleMapInline(admin.TabularInline):
    model = CompetitionModuleStandardModuleMap
    form = CompetitionModuleStandardModuleMapAdminForm
    formset = CompetitionModuleStandardModuleMapInlineFormSet
    extra = 1
    fields = ('module', 'is_primary', 'weight', 'note')
    verbose_name = '标准模块映射'
    verbose_name_plural = '标准模块映射（请确保一条且仅一条主映射）'


class CompetitionModuleAxisMapInline(admin.TabularInline):
    model = CompetitionModuleAxisMap
    form = CompetitionModuleAxisMapAdminForm
    formset = CompetitionModuleAxisMapInlineFormSet
    extra = 1
    fields = ('module_axis', 'is_primary', 'weight', 'note')
    verbose_name = '模块主线映射'
    verbose_name_plural = '模块主线映射（可为空；若配置则需确保一条且仅一条主映射）'


@admin.register(CompetitionModule)
class CompetitionModuleAdmin(admin.ModelAdmin):
    search_fields = (
        'code',
        'name',
        'competition_project__competition__name',
        'competition_project__competition__code',
        'competition_project__project__name',
        'competition_project__project__code',
        'module_mappings__module__name',
        'module_mappings__module__code',
    )
    list_display = (
        'competition_display',
        'competition_project',
        'code',
        'name',
        'primary_standard_module_display',
        'primary_axis_display',
        'mapped_modules_display',
        'mapped_axes_display',
        'sort_order',
    )
    list_display_links = ('code', 'name')
    list_filter = ('competition_project__competition', 'competition_project__project', 'competition_project')
    autocomplete_fields = ['competition_project']
    list_select_related = ('competition_project__competition', 'competition_project__project')
    ordering = (
        '-competition_project__competition__start_date',
        'competition_project__competition__name',
        'competition_project__project__name',
        'sort_order',
        'code',
    )
    fields = ('competition_project', 'sort_order', 'code', 'name', 'description')
    inlines = [CompetitionModuleStandardModuleMapInline, CompetitionModuleAxisMapInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'competition_project__competition',
            'competition_project__project',
        ).prefetch_related('module_mappings__module__module_set', 'axis_mappings__module_axis')

    @admin.display(description='赛事', ordering='competition_project__competition__name')
    def competition_display(self, obj):
        return obj.competition_project.competition

    @admin.display(description='主映射标准模块')
    def primary_standard_module_display(self, obj):
        primary_standard_module = obj.primary_standard_module
        if primary_standard_module is None:
            return '-'
        return format_standard_module_label(primary_standard_module)

    @admin.display(description='主映射主线')
    def primary_axis_display(self, obj):
        primary_axis = obj.primary_axis
        if primary_axis is None:
            return '-'
        return format_module_axis_label(primary_axis)

    @admin.display(description='全部映射')
    def mapped_modules_display(self, obj):
        return format_competition_module_mappings(obj)

    @admin.display(description='全部主线')
    def mapped_axes_display(self, obj):
        return format_competition_module_axis_mappings(obj)


@admin.register(CompetitionModuleStandardModuleMap)
class CompetitionModuleStandardModuleMapAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    search_fields = (
        'competition_module__code',
        'competition_module__name',
        'module__code',
        'module__name',
    )
    list_display = ('competition_module', 'module', 'is_primary', 'weight')
    list_filter = ('is_primary', 'module__project', 'module__module_set')
    autocomplete_fields = ['competition_module']


@admin.register(CompetitionModuleAxisMap)
class CompetitionModuleAxisMapAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    search_fields = (
        'competition_module__code',
        'competition_module__name',
        'module_axis__code',
        'module_axis__name',
    )
    list_display = ('competition_module', 'module_axis', 'is_primary', 'weight')
    list_filter = ('is_primary', 'module_axis__project', 'module_axis')
    autocomplete_fields = ['competition_module', 'module_axis']


@admin.register(CompetitorUser)
class CompetitorUserAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    search_fields = ('username', 'first_name')
    list_display = ('username', 'first_name', 'email')


@admin.register(Competitor)
class CompetitorAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    form = CompetitorAdminForm
    list_display = ('name', 'gender', 'member', 'organization', 'competition_project', 'user', 'created_at')
    list_filter = ('member', 'gender', 'competition_project__competition')
    search_fields = ('person__name', 'member__name', 'person__user__username', 'competition_project__project__name', 'person__organization')
    autocomplete_fields = ['person', 'competition_project']
    list_select_related = ('member', 'competition_project__competition', 'competition_project__project', 'person__user')


@admin.register(SkillPosition)
class SkillPositionAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    form = SkillPositionAdminForm
    list_display = ('name', 'position_name', 'competition_project', 'organization', 'user')
    list_filter = ('competition_project', 'position_name')
    search_fields = ('person__name', 'position_name', 'person__user__username', 'person__organization')
    autocomplete_fields = ['person', 'competition_project']
    list_select_related = ('competition_project__competition', 'competition_project__project', 'person__user')


@admin.register(Expert)
class ExpertAdmin(HiddenFromAdminIndexMixin, admin.ModelAdmin):
    form = ExpertAdminForm
    list_display = ('name', 'user', 'member', 'competition_project', 'organization')
    list_filter = ('member', 'competition_project')
    search_fields = ('person__name', 'person__user__username', 'member__name', 'person__organization')
    autocomplete_fields = ['person', 'competition_project']
    list_select_related = ('member', 'competition_project__competition', 'competition_project__project', 'person__user')

