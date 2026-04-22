from django import forms
from django.db.models import Q

from core.utils.forms import StyledFormMixin

from .models import CompetitionPerson, CompetitionProject, CompetitionResult, Competitor, CompetitorUser, Expert, Member, SkillPosition


def get_competition_project_queryset():
    return CompetitionProject.objects.select_related(
        'competition__competition_type',
        'project',
    ).order_by('-competition__start_date', 'competition__name', 'project__name')


def get_member_queryset(competition_project):
    if competition_project is None:
        return Member.objects.none()
    required_level = competition_project.required_member_level
    if required_level is None:
        return Member.objects.none()
    return Member.objects.filter(level=required_level).order_by('level', 'name')


def get_competitor_user_queryset():
    return CompetitorUser.objects.order_by('last_name', 'first_name', 'username')


def get_competition_person_queryset():
    return CompetitionPerson.objects.select_related('user').order_by('name', 'organization', 'pk')


def format_competition_person_label(person):
    parts = [person.name]
    if person.organization:
        parts.append(person.organization)
    if person.user_id:
        parts.append(person.user.display_name)
    return ' / '.join(parts)


def get_available_competitor_queryset(competition_project, include_competitor=None):
    queryset = Competitor.objects.select_related(
        'member',
        'person__user',
        'competition_project__competition',
        'competition_project__project',
    )
    if competition_project is None:
        return queryset.none()

    queryset = queryset.filter(competition_project=competition_project)
    if include_competitor is not None and include_competitor.pk:
        return queryset.filter(Q(results__isnull=True) | Q(pk=include_competitor.pk)).distinct().order_by(
            'person__name',
            'pk',
        )
    return queryset.filter(results__isnull=True).order_by('person__name', 'pk')


class CompetitionProjectFormMixin:
    competition_project_field_name = 'competition_project'

    def get_selected_competition_project(self):
        queryset = get_competition_project_queryset()
        if self.is_bound:
            value = self.data.get(self.add_prefix(self.competition_project_field_name))
            if value:
                return queryset.filter(pk=value).first()

        initial_value = self.initial.get(self.competition_project_field_name)
        if initial_value:
            return queryset.filter(pk=initial_value).first()

        competition_project_id = getattr(self.instance, 'competition_project_id', None)
        if competition_project_id:
            return self.instance.competition_project
        return None

    def init_competition_project_field(self):
        field = self.fields.get(self.competition_project_field_name)
        if field is None:
            return

        field.queryset = get_competition_project_queryset()
        field.label_from_instance = lambda obj: f'{obj.competition.name} / {obj.project.name}'


class CompetitionPersonAssignmentFormMixin:
    person_noun = '人员'
    person_field_label = '已有人员'
    new_person_name_label = '新增人员姓名'
    new_person_organization_label = '新增人员所属单位'
    new_person_user_label = '新增人员关联用户'

    def init_person_fields(self):
        if 'new_person_name' not in self.fields:
            self.fields['new_person_name'] = forms.CharField(required=False, max_length=100)
        if 'new_person_organization' not in self.fields:
            self.fields['new_person_organization'] = forms.CharField(required=False, max_length=100)
        if 'new_person_user' not in self.fields:
            self.fields['new_person_user'] = forms.ModelChoiceField(
                queryset=CompetitorUser.objects.none(),
                required=False,
            )

        self.fields['person'].queryset = get_competition_person_queryset()
        self.fields['person'].required = False
        self.fields['person'].label = self.person_field_label
        self.fields['person'].help_text = f'如已录入{self.person_noun}主档，可直接选择；如需新建，请留空并填写下方信息。'
        self.fields['person'].label_from_instance = format_competition_person_label

        self.fields['new_person_name'].label = self.new_person_name_label
        self.fields['new_person_name'].help_text = f'仅在未选择已有{self.person_noun}时填写。'
        self.fields['new_person_organization'].label = self.new_person_organization_label
        self.fields['new_person_organization'].help_text = f'仅在新增{self.person_noun}时填写。'
        self.fields['new_person_user'].label = self.new_person_user_label
        self.fields['new_person_user'].queryset = get_competitor_user_queryset()
        self.fields['new_person_user'].label_from_instance = lambda obj: obj.display_name

    def clean(self):
        cleaned_data = super().clean()
        person = cleaned_data.get('person')
        new_person_name = (cleaned_data.get('new_person_name') or '').strip()
        if person is None and not new_person_name:
            message = f'请选择已有{self.person_noun}，或填写新的{self.person_noun}姓名。'
            self.add_error('person', message)
            self.add_error('new_person_name', message)
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        person = self.cleaned_data.get('person')
        if person is None:
            person = CompetitionPerson.objects.create(
                name=self.cleaned_data['new_person_name'].strip(),
                organization=(self.cleaned_data.get('new_person_organization') or '').strip(),
                user=self.cleaned_data.get('new_person_user'),
            )
        instance.person = person
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class MemberCreateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Member
        fields = ['name', 'code', 'level', 'flag']


class CompetitorCreateForm(CompetitionPersonAssignmentFormMixin, CompetitionProjectFormMixin, StyledFormMixin, forms.ModelForm):
    person_noun = '选手'
    person_field_label = '已有选手'
    new_person_name_label = '新增选手姓名'
    new_person_organization_label = '新增选手所属单位'
    new_person_user_label = '新增选手关联用户'

    class Meta:
        model = Competitor
        fields = ['competition_project', 'person', 'member', 'gender']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_competition_project_field()
        self.init_person_fields()
        self.order_fields([
            'competition_project',
            'person',
            'new_person_name',
            'new_person_organization',
            'new_person_user',
            'member',
            'gender',
        ])

        competition_project = self.get_selected_competition_project()
        self.fields['member'].queryset = get_member_queryset(competition_project)
        self.fields['member'].label_from_instance = lambda obj: f'{obj.name} [{obj.get_level_display()}]'
        if competition_project is None:
            self.fields['member'].help_text = '请先选择具体赛项，再选择匹配层级的代表队。'
        else:
            self.fields['member'].help_text = f'当前赛事级别要求选择“{competition_project.required_member_level_label}”代表队。'


class ExpertCreateForm(CompetitionPersonAssignmentFormMixin, CompetitionProjectFormMixin, StyledFormMixin, forms.ModelForm):
    person_noun = '专家'
    person_field_label = '已有专家'
    new_person_name_label = '新增专家姓名'
    new_person_organization_label = '新增专家所属单位'
    new_person_user_label = '新增专家关联用户'

    class Meta:
        model = Expert
        fields = ['competition_project', 'person', 'member']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_competition_project_field()
        self.init_person_fields()
        self.order_fields([
            'competition_project',
            'person',
            'new_person_name',
            'new_person_organization',
            'new_person_user',
            'member',
        ])

        competition_project = self.get_selected_competition_project()
        self.fields['member'].queryset = get_member_queryset(competition_project)
        self.fields['member'].label_from_instance = lambda obj: f'{obj.name} [{obj.get_level_display()}]'
        if competition_project is None:
            self.fields['member'].help_text = '请先选择具体赛项，再选择匹配层级的代表队。'
        else:
            self.fields['member'].help_text = f'当前赛事级别要求选择“{competition_project.required_member_level_label}”代表队。'


class SkillPositionCreateForm(CompetitionPersonAssignmentFormMixin, CompetitionProjectFormMixin, StyledFormMixin, forms.ModelForm):
    person_noun = '岗位人员'
    person_field_label = '已有岗位人员'
    new_person_name_label = '新增岗位人员姓名'
    new_person_organization_label = '新增岗位人员所属单位'
    new_person_user_label = '新增岗位人员关联用户'

    class Meta:
        model = SkillPosition
        fields = ['competition_project', 'person', 'position_name', 'remarks']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_competition_project_field()
        self.init_person_fields()
        self.order_fields([
            'competition_project',
            'person',
            'new_person_name',
            'new_person_organization',
            'new_person_user',
            'position_name',
            'remarks',
        ])


class CompetitionResultCreateForm(CompetitionProjectFormMixin, StyledFormMixin, forms.ModelForm):
    competition_project = forms.ModelChoiceField(
        label='具体赛项',
        queryset=CompetitionProject.objects.none(),
        help_text='先选择具体赛项，再录入该赛项下尚未归档总成绩的选手。',
    )

    class Meta:
        model = CompetitionResult
        fields = ['competition_project', 'competitor', 'score_100', 'score_700', 'rank', 'medal']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_competition_project_field()

        competition_project = self.get_selected_competition_project()
        include_competitor = self.instance.competitor if getattr(self.instance, 'competitor_id', None) else None
        self.fields['competitor'].queryset = get_available_competitor_queryset(
            competition_project,
            include_competitor=include_competitor,
        )
        self.fields['competitor'].label_from_instance = (
            lambda obj: f'{obj.name} / {obj.member.name}'
        )
        if competition_project is None:
            self.fields['competitor'].help_text = '请先选择具体赛项。'
        else:
            self.fields['competitor'].help_text = '只显示该赛项下尚未录入最终总成绩的选手。'

    def clean(self):
        cleaned_data = super().clean()
        competition_project = cleaned_data.get('competition_project')
        competitor = cleaned_data.get('competitor')
        if competition_project is not None and competitor is not None and competitor.competition_project_id != competition_project.pk:
            self.add_error('competitor', '所选选手不属于当前具体赛项。')
        return cleaned_data