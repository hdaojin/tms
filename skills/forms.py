from decimal import Decimal

from django import forms
from django.db import transaction
from django.urls import reverse

from competition_standards.models import StandardModule
from competitions.models import CompetitionProject
from core.utils.forms import StyledFormMixin
from .models import ExamPoint, ExamPointSkill, Skill, Topic


TOPIC_MODE_EXISTING = 'existing'
TOPIC_MODE_NEW = 'new'
TOPIC_MODE_CHOICES = (
    (TOPIC_MODE_EXISTING, '选择已有专题'),
    (TOPIC_MODE_NEW, '新建专题'),
)


def get_competition_project_modules_queryset(competition_project):
    if competition_project is None:
        return StandardModule.objects.none()
    return (
        StandardModule.objects.current().filter(
            competition_module_mappings__competition_module__competition_project=competition_project,
        )
        .select_related('project', 'module_set')
        .distinct()
        .order_by('code', 'name')
    )


class SkillFilterForm(StyledFormMixin, forms.Form):
    module = forms.ModelChoiceField(
        label="标准模块",
        queryset=StandardModule.objects.none(),
        required=False,
        empty_label="全部模块",
    )
    keyword = forms.CharField(
        label="关键字",
        required=False,
        max_length=100,
        help_text="支持匹配专题、技能点和描述。",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['module'].queryset = StandardModule.objects.current().select_related('project', 'module_set').order_by(
            'project__name', 'module_set__sort_order', 'sort_order', 'code', 'name'
        )
        self.fields['keyword'].widget.attrs.setdefault('placeholder', '输入专题或技能点关键字')


class ExamPointEntryForm(StyledFormMixin, forms.Form):
    competition_project = forms.ModelChoiceField(
        label='具体赛项',
        queryset=CompetitionProject.objects.none(),
        help_text='先选择具体赛项，系统会只提供该赛项已配置的模块。',
    )
    module = forms.ModelChoiceField(
        label='标准模块',
        queryset=StandardModule.objects.none(),
        help_text='标准模块来自当前具体赛项的本届官方模块映射到当前标准模块版本后的结果。',
    )
    topic_mode = forms.ChoiceField(
        label='新增技能点专题处理方式',
        choices=TOPIC_MODE_CHOICES,
        initial=TOPIC_MODE_EXISTING,
        widget=forms.RadioSelect,
    )
    existing_topic = forms.ModelChoiceField(
        label='新增技能点归属到已有专题',
        queryset=Topic.objects.none(),
        required=False,
        empty_label='请选择专题',
        help_text='只有在补录新技能点时，才需要指定其归属专题。',
    )
    new_topic_name = forms.CharField(
        label='新增技能点归属到新专题',
        required=False,
        max_length=100,
        help_text='输入后会提示当前模块下已有的相近专题。',
    )
    new_topic_description = forms.CharField(
        label='新专题描述',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )
    existing_skills = forms.ModelMultipleChoiceField(
        label='已有技能点',
        queryset=Skill.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='可直接复用当前模块下多个专题的技能点，适合录入综合考点。',
    )
    name = forms.CharField(
        label='考点名称',
        max_length=500,
        help_text='同一竞赛下名称必须唯一。',
    )
    detail_content = forms.CharField(
        label='详细内容',
        required=False,
        widget=forms.Textarea(attrs={'rows': 5}),
    )
    difficulty = forms.IntegerField(
        label='难度系数',
        min_value=1,
        max_value=5,
        initial=3,
        help_text='1 最简单，5 最难。',
    )
    score = forms.DecimalField(
        label='分值',
        max_digits=10,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        min_value=Decimal('0.00'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.save_summary = {}
        self.new_skill_names = []

        self.fields['competition_project'].queryset = CompetitionProject.objects.select_related(
            'competition',
            'project',
        ).order_by('-competition__start_date', 'competition__name', 'project__name')
        self.fields['competition_project'].label_from_instance = (
            lambda obj: f'{obj.competition.name} / {obj.project.name}'
        )

        selected_competition_project = self._get_selected_instance(
            'competition_project',
            self.fields['competition_project'].queryset,
        )
        self.fields['module'].queryset = get_competition_project_modules_queryset(selected_competition_project)
        self.fields['module'].label_from_instance = (
            lambda obj: f'{obj.code} - {obj.name}'
        )

        selected_module = self._get_selected_instance('module', self.fields['module'].queryset)
        self.fields['existing_topic'].queryset = Topic.objects.filter(module=selected_module).order_by(
            'name'
        )
        self.fields['existing_topic'].label_from_instance = lambda obj: obj.name

        selected_topic_mode = self._get_selected_value('topic_mode') or TOPIC_MODE_EXISTING
        selected_existing_topic = self._get_selected_instance(
            'existing_topic',
            self.fields['existing_topic'].queryset,
        )
        if selected_module is not None:
            self.fields['existing_skills'].queryset = Skill.objects.filter(
                topic__module=selected_module
            ).select_related('topic').order_by('topic__name', 'name')
        else:
            self.fields['existing_skills'].queryset = Skill.objects.none()
        self.fields['existing_skills'].label_from_instance = lambda obj: f'{obj.topic.name} / {obj.name}'

        self.fields['competition_project'].widget.attrs.update(
            {
                'hx-get': reverse('skills:exam_point_dependency_fields'),
                'hx-trigger': 'change',
                'hx-target': '#entry-dependencies',
                'hx-swap': 'innerHTML',
                'hx-include': '#exam-point-entry-form',
                'x-on:change': "topicMode = 'existing'; newSkills = [''];",
            }
        )
        self.fields['module'].widget.attrs.update(
            {
                'hx-get': reverse('skills:exam_point_dependency_fields'),
                'hx-trigger': 'change',
                'hx-target': '#entry-dependencies',
                'hx-swap': 'innerHTML',
                'hx-include': '#exam-point-entry-form',
                'x-on:change': "topicMode = 'existing'; newSkills = [''];",
            }
        )
        self.fields['topic_mode'].widget.attrs.update(
            {
                'x-model': 'topicMode',
                'x-on:change': "newSkills = [''];",
            }
        )
        self.fields['new_topic_name'].widget.attrs.update(
            {
                'placeholder': '例如：网络安全基础',
                'hx-get': reverse('skills:exam_point_topic_suggestions'),
                'hx-trigger': 'input changed delay:300ms',
                'hx-target': '#topic-suggestions',
                'hx-swap': 'innerHTML',
                'hx-include': '#exam-point-entry-form',
            }
        )
        self.fields['name'].widget.attrs.update(
            {
                'placeholder': '例如：基于 OpenLDAP 的 OpenVPN 用户认证接入',
                'hx-get': reverse('skills:exam_point_name_suggestions'),
                'hx-trigger': 'input changed delay:300ms',
                'hx-target': '#exam-point-suggestions',
                'hx-swap': 'innerHTML',
                'hx-include': '#exam-point-entry-form',
            }
        )
        self.fields['score'].widget.attrs.update({'step': '0.01'})

        if selected_competition_project is None:
            self.fields['module'].widget.attrs['disabled'] = True
        else:
            self.fields['module'].widget.attrs.pop('disabled', None)

        if selected_module is None or selected_topic_mode != TOPIC_MODE_EXISTING:
            self.fields['existing_topic'].widget.attrs['disabled'] = True
        else:
            self.fields['existing_topic'].widget.attrs.pop('disabled', None)

        if selected_module is None:
            self.fields['existing_skills'].widget.attrs['disabled'] = True
        else:
            self.fields['existing_skills'].widget.attrs.pop('disabled', None)

        self.has_available_modules = self.fields['module'].queryset.exists()
        self.has_existing_topics = self.fields['existing_topic'].queryset.exists()
        self.has_existing_skills = self.fields['existing_skills'].queryset.exists()

    def _get_selected_value(self, field_name):
        if self.is_bound:
            return self.data.get(field_name)
        return self.initial.get(field_name) or self.fields[field_name].initial

    def _get_selected_instance(self, field_name, queryset):
        selected_value = self._get_selected_value(field_name)
        if not selected_value:
            return None
        try:
            return queryset.get(pk=selected_value)
        except (queryset.model.DoesNotExist, ValueError, TypeError):
            return None

    def _parse_new_skill_names(self):
        seen = set()
        skill_names = []
        for raw_value in self.data.getlist('new_skill_names'):
            skill_name = raw_value.strip()
            if not skill_name:
                continue
            if skill_name in seen:
                continue
            seen.add(skill_name)
            skill_names.append(skill_name)
        return skill_names

    def clean(self):
        cleaned_data = super().clean()
        self.new_skill_names = self._parse_new_skill_names() if self.is_bound else []

        competition_project = cleaned_data.get('competition_project')
        module = cleaned_data.get('module')
        topic_mode = cleaned_data.get('topic_mode') or TOPIC_MODE_EXISTING
        existing_topic = cleaned_data.get('existing_topic')
        existing_skills = list(cleaned_data.get('existing_skills') or [])
        exam_point_name = (cleaned_data.get('name') or '').strip()

        resolved_topic = None
        if competition_project and module:
            if not get_competition_project_modules_queryset(competition_project).filter(pk=module.pk).exists():
                self.add_error('module', '该模块不属于当前具体赛项已配置的赛项模块。')

        if module is not None:
            invalid_skill = next(
                (skill for skill in existing_skills if skill.topic.module_id != module.pk),
                None,
            )
            if invalid_skill is not None:
                self.add_error('existing_skills', '所选技能点必须全部属于当前模块。')

        if existing_topic is not None and module is not None and existing_topic.module_id != module.pk:
            self.add_error('existing_topic', '所选专题不属于当前模块。')

        if self.new_skill_names:
            if topic_mode == TOPIC_MODE_EXISTING:
                if existing_topic is None:
                    self.add_error('existing_topic', '请选择新增技能点归属的已有专题。')
                else:
                    resolved_topic = existing_topic
            else:
                topic_name = (cleaned_data.get('new_topic_name') or '').strip()
                if not topic_name:
                    self.add_error('new_topic_name', '请输入专题名称。')
                elif module is not None:
                    resolved_topic = Topic.objects.filter(module=module, name=topic_name).first()

        if not existing_skills and not self.new_skill_names:
            self.add_error('existing_skills', '请至少选择一个已有技能点，或新增一个技能点。')

        if competition_project is not None and exam_point_name:
            if ExamPoint.objects.filter(competition_project=competition_project, name=exam_point_name).exists():
                self.add_error('name', '当前具体赛项下已存在同名考点，请直接复用或改用新名称。')

        cleaned_data['resolved_topic'] = resolved_topic
        cleaned_data['new_skill_names'] = self.new_skill_names
        return cleaned_data

    @transaction.atomic
    def save(self):
        competition_project = self.cleaned_data['competition_project']
        module = self.cleaned_data['module']
        resolved_topic = self.cleaned_data.get('resolved_topic')
        topic_created = False

        if self.cleaned_data.get('new_skill_names') and resolved_topic is None:
            resolved_topic, topic_created = Topic.objects.get_or_create(
                module=module,
                name=self.cleaned_data['new_topic_name'].strip(),
                defaults={
                    'description': (self.cleaned_data.get('new_topic_description') or '').strip(),
                },
            )

        skill_map = {skill.pk: skill for skill in self.cleaned_data.get('existing_skills', [])}
        created_skill_count = 0
        reused_skill_count = 0
        for skill_name in self.cleaned_data.get('new_skill_names', []):
            skill, created = Skill.objects.get_or_create(
                topic=resolved_topic,
                name=skill_name,
            )
            if skill.pk not in skill_map:
                skill_map[skill.pk] = skill
            if created:
                created_skill_count += 1
            else:
                reused_skill_count += 1

        selected_skills = list(skill_map.values())

        exam_point = ExamPoint.objects.create(
            competition_project=competition_project,
            name=self.cleaned_data['name'],
            detail_content=(self.cleaned_data.get('detail_content') or '').strip(),
            difficulty=self.cleaned_data['difficulty'],
            score=self.cleaned_data.get('score') or Decimal('0.00'),
        )

        default_primary = len(selected_skills) == 1
        ExamPointSkill.objects.bulk_create(
            [
                ExamPointSkill(
                    exam_point=exam_point,
                    skill=skill,
                    is_primary=default_primary,
                    weight=Decimal('1.00'),
                )
                for skill in selected_skills
            ]
        )

        self.save_summary = {
            'module': module,
            'topic': resolved_topic,
            'topic_created': topic_created,
            'created_skill_count': created_skill_count,
            'reused_skill_count': reused_skill_count,
            'skill_count': len(selected_skills),
        }
        return exam_point
