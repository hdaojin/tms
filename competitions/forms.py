from django import forms
from django.core.exceptions import ValidationError

from accounts.services.users import get_user_display_name
from core.utils.forms import StyledFormMixin

from .models import CompetitionProject, CompetitionResult, Competitor, CompetitorUser, Expert, Member, SkillPosition
from .selectors import (
    format_competition_project_label,
    format_competition_person_label,
    format_competitor_label,
    format_member_label,
    get_available_competition_people_for_competition_project,
    get_available_competitors_for_competition_project,
    get_available_members_for_competition_project,
    get_competition_person_queryset,
    get_competition_project_queryset,
    get_competitor_user_queryset,
    get_members_for_competition_project,
)
from .services import (
    create_or_link_competition_project_member,
    resolve_or_create_competition_person,
)


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
        field.label_from_instance = format_competition_project_label


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
        self.fields['new_person_user'].label_from_instance = get_user_display_name

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
        instance.person = resolve_or_create_competition_person(
            person=self.cleaned_data.get('person'),
            new_person_name=self.cleaned_data.get('new_person_name') or '',
            new_person_organization=self.cleaned_data.get('new_person_organization') or '',
            new_person_user=self.cleaned_data.get('new_person_user'),
        )
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CompetitionProjectMemberLinkForm(StyledFormMixin, forms.Form):
    existing_member = forms.ModelChoiceField(
        label='已有代表队',
        queryset=Member.objects.none(),
        required=False,
    )
    new_member_name = forms.CharField(label='新增代表队名称', max_length=100, required=False)
    new_member_code = forms.CharField(label='新增代表队代码', max_length=20, required=False)
    new_member_flag = forms.ImageField(label='新增代表队旗帜', required=False)

    def __init__(self, *args, competition_project, **kwargs):
        self.competition_project = competition_project
        super().__init__(*args, **kwargs)
        self.fields['existing_member'].queryset = get_available_members_for_competition_project(competition_project)
        self.fields['existing_member'].label_from_instance = format_member_label
        self.fields['existing_member'].help_text = (
            f'当前赛项要求选择“{competition_project.required_member_level_label}”代表队。'
            '如库中已有，可直接选择并关联到当前赛项。'
        )
        self.fields['new_member_name'].help_text = '仅在未选择已有代表队时填写。'
        self.fields['new_member_code'].help_text = '仅在未选择已有代表队时填写，代码需全局唯一。'
        self.fields['new_member_flag'].help_text = '仅在新增代表队时填写。'
        self.order_fields([
            'existing_member',
            'new_member_name',
            'new_member_code',
            'new_member_flag',
        ])

    def clean(self):
        cleaned_data = super().clean()
        existing_member = cleaned_data.get('existing_member')
        new_member_name = (cleaned_data.get('new_member_name') or '').strip()
        new_member_code = (cleaned_data.get('new_member_code') or '').strip()
        new_member_flag = cleaned_data.get('new_member_flag')
        has_new_member_input = bool(new_member_name or new_member_code or new_member_flag)

        if existing_member and has_new_member_input:
            raise forms.ValidationError('请选择已有代表队，或填写下方新增代表队信息，两种方式不能同时使用。')

        if existing_member is None and not has_new_member_input:
            message = '请选择已有代表队，或填写新的代表队名称和代码。'
            self.add_error('existing_member', message)
            self.add_error('new_member_name', message)
            self.add_error('new_member_code', message)
            return cleaned_data

        if existing_member is not None:
            return cleaned_data

        if not new_member_name:
            self.add_error('new_member_name', '请输入新的代表队名称。')
        if not new_member_code:
            self.add_error('new_member_code', '请输入新的代表队代码。')
        if self.errors:
            return cleaned_data

        member = Member(
            name=new_member_name,
            code=new_member_code,
            level=self.competition_project.required_member_level,
            flag=new_member_flag,
        )
        try:
            member.full_clean()
        except ValidationError as exc:
            field_mapping = {
                'name': 'new_member_name',
                'code': 'new_member_code',
                'flag': 'new_member_flag',
            }
            for field_name, messages in exc.message_dict.items():
                target_field = field_mapping.get(field_name)
                if target_field:
                    for message in messages:
                        self.add_error(target_field, message)
                else:
                    for message in messages:
                        self.add_error(None, message)

        cleaned_data['new_member_name'] = new_member_name
        cleaned_data['new_member_code'] = new_member_code
        return cleaned_data

    def save(self):
        return create_or_link_competition_project_member(
            competition_project=self.competition_project,
            existing_member=self.cleaned_data.get('existing_member'),
            new_member_name=self.cleaned_data.get('new_member_name') or '',
            new_member_code=self.cleaned_data.get('new_member_code') or '',
            new_member_flag=self.cleaned_data.get('new_member_flag'),
        )


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
        self.fixed_competition_project = kwargs.pop('competition_project', None)
        super().__init__(*args, **kwargs)
        if self.fixed_competition_project is None:
            self.init_competition_project_field()
        self.init_person_fields()
        competition_project = self.fixed_competition_project or self.get_selected_competition_project()

        if self.fixed_competition_project is not None:
            self.fields.pop('competition_project', None)
            self.fields['person'].queryset = get_available_competition_people_for_competition_project(competition_project)
            self.fields['person'].help_text = '如该选手参加过往届或已在人员库中，可直接选择；通常请直接填写下方新增选手信息。'
            self.fields['new_person_name'].help_text = '默认直接新增本届选手；仅在上方未选择已有选手时填写。'
            self.fields['new_person_organization'].help_text = '仅在新增选手时填写。'
            self.fields['new_person_user'].help_text = '仅在新增选手且需要关联校内账号时填写。'
            self.order_fields([
                'new_person_name',
                'new_person_organization',
                'new_person_user',
                'person',
                'member',
                'gender',
            ])
        else:
            self.order_fields([
                'competition_project',
                'person',
                'new_person_name',
                'new_person_organization',
                'new_person_user',
                'member',
                'gender',
            ])

        self.fields['member'].queryset = get_members_for_competition_project(competition_project)
        self.fields['member'].label_from_instance = format_member_label
        if competition_project is None:
            self.fields['member'].help_text = '请先选择具体赛项，再选择匹配层级的代表队。'
        else:
            self.fields['member'].help_text = (
                f'当前赛事级别要求选择“{competition_project.required_member_level_label}”代表队。'
                '这里只显示当前赛项已关联的代表队。'
            )

    def save(self, commit=True):
        if self.fixed_competition_project is None:
            return super().save(commit=commit)

        instance = super().save(commit=False)
        instance.competition_project = self.fixed_competition_project
        if commit:
            instance.save()
            self.save_m2m()
        return instance


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
        self.fields['member'].queryset = get_members_for_competition_project(competition_project)
        self.fields['member'].label_from_instance = format_member_label
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
        self.fields['competitor'].queryset = get_available_competitors_for_competition_project(
            competition_project,
            include_competitor=include_competitor,
        )
        self.fields['competitor'].label_from_instance = format_competitor_label
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