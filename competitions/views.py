from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, DetailView, FormView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .forms import (
	CompetitionProjectMemberLinkForm,
	CompetitionResultCreateForm,
	CompetitorCreateForm,
	ExpertCreateForm,
	SkillPositionCreateForm,
)
from .models import Competition, CompetitionProject, CompetitionResult, Competitor, Expert, SkillPosition
from .selectors import (
	get_competition_project_competitors_queryset,
	get_competition_project_experts_queryset,
	get_competition_project_official_modules_queryset,
	get_competition_project_queryset,
	get_competition_project_results_queryset,
	get_competition_project_skill_positions_queryset,
	get_competition_projects_for_competition,
	get_members_for_competition_project,
)
from .tables import CompetitionTable


def build_competition_project_url(name, competition_project_id, next_url=None):
	params = {'competition_project': competition_project_id}
	if next_url:
		params['next'] = next_url
	return f"{reverse(name)}?{urlencode(params)}"


class CompetitionProjectScopedPathMixin:
	competition_project_url_kwarg = 'pk'
	competition_project_form_kwarg = 'competition_project'

	def get_competition_project_queryset(self):
		return get_competition_project_queryset()

	def get_competition_project(self):
		if not hasattr(self, '_competition_project'):
			self._competition_project = get_object_or_404(
				self.get_competition_project_queryset(),
				pk=self.kwargs[self.competition_project_url_kwarg],
			)
		return self._competition_project

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs[self.competition_project_form_kwarg] = self.get_competition_project()
		return kwargs

	def get_competition_project_detail_url(self):
		return reverse('competitions:competitionproject_detail', args=[self.get_competition_project().pk])


class CompetitionListView(TitleMixin, LoginRequiredMixin, SingleTableView):
	model = Competition
	table_class = CompetitionTable
	template_name = 'competitions/competition_list.html'
	table_pagination = {"per_page": 20}
	title = '竞赛列表'
	title_icon = 'icon-[tabler--trophy]'

	def get_queryset(self):
		return super().get_queryset().select_related('competition_type').annotate(
			competition_project_total=Count('competition_projects', distinct=True),
		)


class CompetitionDetailView(TitleMixin, LoginRequiredMixin, DetailView):
	model = Competition
	template_name = 'competitions/competition_detail.html'
	context_object_name = 'competition'
	title = '{name}'
	title_icon = 'icon-[tabler--trophy]'

	def get_queryset(self):
		return super().get_queryset().select_related('competition_type')

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['competition_projects'] = get_competition_projects_for_competition(self.object)
		return context


class CompetitionProjectDetailView(TitleMixin, LoginRequiredMixin, DetailView):
	model = CompetitionProject
	template_name = 'competitions/competitionproject_detail.html'
	context_object_name = 'competition_project'
	title = '{competition} - {project}'
	title_icon = 'icon-[tabler--list-details]'

	def get_queryset(self):
		return super().get_queryset().select_related(
			'competition__competition_type',
			'project',
		).prefetch_related(
			'competition_modules__module_mappings__module__module_set',
			'member_links__member',
			'competitors__member',
			'competitors__person__user',
			'experts__member',
			'experts__person__user',
			'skill_positions__person__user',
		)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		competition_project = self.object
		detail_url = reverse('competitions:competitionproject_detail', args=[competition_project.pk])

		context['official_modules'] = get_competition_project_official_modules_queryset(competition_project)
		context['competitors'] = get_competition_project_competitors_queryset(competition_project)
		context['experts'] = get_competition_project_experts_queryset(competition_project)
		context['skill_positions'] = get_competition_project_skill_positions_queryset(competition_project)
		context['results'] = get_competition_project_results_queryset(competition_project)
		context['members'] = get_members_for_competition_project(competition_project)
		context['member_link_url'] = reverse('competitions:competitionproject_member_create', args=[competition_project.pk])
		context['competitor_create_url'] = reverse('competitions:competitor_create', args=[competition_project.pk])
		context['expert_create_url'] = build_competition_project_url(
			'competitions:expert_create',
			competition_project.pk,
			detail_url,
		)
		context['skillposition_create_url'] = build_competition_project_url(
			'competitions:skillposition_create',
			competition_project.pk,
			detail_url,
		)
		context['competitionresult_create_url'] = build_competition_project_url(
			'competitions:competitionresult_create',
			competition_project.pk,
			detail_url,
		)
		return context


class CompetitionCreateViewMixin(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
	raise_exception = True
	template_name = 'competitions/create_form.html'
	submit_label = '保存'
	success_message = '保存成功。'
	page_note = ''

	def get_initial(self):
		initial = super().get_initial()
		if 'competition_project' in getattr(self.form_class, 'base_fields', {}):
			competition_project_id = self.request.GET.get('competition_project')
			if competition_project_id:
				initial['competition_project'] = competition_project_id
		return initial

	def get_next_url(self):
		next_url = self.request.POST.get('next') or self.request.GET.get('next')
		if not next_url:
			return None
		if not url_has_allowed_host_and_scheme(
			next_url,
			allowed_hosts={self.request.get_host()},
			require_https=self.request.is_secure(),
		):
			return None
		return next_url

	def get_back_url(self):
		return self.get_next_url() or reverse('competitions:competition_list')

	def get_success_url(self):
		return self.get_next_url() or self.get_default_success_url()

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['back_url'] = self.get_back_url()
		context['next_url'] = self.get_next_url()
		context['submit_label'] = self.submit_label
		context['page_note'] = self.page_note
		return context

	def form_valid(self, form):
		response = super().form_valid(form)
		messages.success(self.request, self.success_message)
		return response


class CompetitionProjectMemberCreateView(CompetitionProjectScopedPathMixin, TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, FormView):
	raise_exception = True
	template_name = 'competitions/create_form.html'
	form_class = CompetitionProjectMemberLinkForm
	permission_required = 'competitions.add_member'
	title = '关联代表队'
	title_icon = 'icon-[tabler--flag]'
	submit_label = '保存'

	def get_back_url(self):
		return self.get_competition_project_detail_url()

	def get_success_url(self):
		return self.get_back_url()

	def get_page_note(self):
		competition_project = self.get_competition_project()
		return (
			f'当前赛项要求选择“{competition_project.required_member_level_label}”代表队。'
			'优先选择已有代表队并关联到当前赛项；如库中没有，再在下方补录新的代表队。'
		)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['back_url'] = self.get_back_url()
		context['next_url'] = None
		context['submit_label'] = self.submit_label
		context['page_note'] = self.get_page_note()
		return context

	def form_valid(self, form):
		link = form.save()
		if form.cleaned_data.get('existing_member') is not None:
			messages.success(self.request, f'代表队“{link.member.name}”已关联到当前赛项。')
		else:
			messages.success(self.request, f'代表队“{link.member.name}”已创建并关联到当前赛项。')
		return super().form_valid(form)


class CompetitorCreateView(CompetitionProjectScopedPathMixin, CompetitionCreateViewMixin):
	model = Competitor
	form_class = CompetitorCreateForm
	permission_required = 'competitions.add_competitor'
	title = '新增选手'
	title_icon = 'icon-[tabler--user-plus]'
	submit_label = '保存'
	success_message = '选手信息已保存。'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		competition_project = self.get_competition_project()
		context['page_note'] = (
			f'当前正在为“{competition_project.competition.name} / {competition_project.project.name}”新增选手。'
			'默认直接补录本届选手；如该选手曾参加过往届或已在人员库中，再选择已有选手。'
		)
		return context

	def get_default_success_url(self):
		return self.get_competition_project_detail_url()


class ExpertCreateView(CompetitionCreateViewMixin):
	model = Expert
	form_class = ExpertCreateForm
	permission_required = 'competitions.add_expert'
	title = '新增专家'
	title_icon = 'icon-[tabler--user-star]'
	submit_label = '保存专家'
	success_message = '专家信息已保存。'
	page_note = '请先选择具体赛项，系统会自动按赛事级别过滤可选代表队。'

	def get_default_success_url(self):
		return reverse('competitions:competitionproject_detail', args=[self.object.competition_project_id])


class SkillPositionCreateView(CompetitionCreateViewMixin):
	model = SkillPosition
	form_class = SkillPositionCreateForm
	permission_required = 'competitions.add_skillposition'
	title = '新增岗位人员'
	title_icon = 'icon-[tabler--briefcase-2]'
	submit_label = '保存岗位人员'
	success_message = '岗位人员信息已保存。'
	page_note = '技能岗位人员仅补录本届赛事人员信息；赛事类型、标准赛项、标准模块等主干资料仍由管理员维护。'

	def get_default_success_url(self):
		return reverse('competitions:competitionproject_detail', args=[self.object.competition_project_id])


class CompetitionResultCreateView(CompetitionCreateViewMixin):
	model = CompetitionResult
	form_class = CompetitionResultCreateForm
	permission_required = 'competitions.add_competitionresult'
	title = '录入竞赛总成绩'
	title_icon = 'icon-[tabler--chart-bar]'
	submit_label = '保存总成绩'
	success_message = '竞赛总成绩已保存。'
	page_note = '模块级成绩由 assessment 管理，这里只录入最终归档总成绩、排名和奖项。'

	def get_default_success_url(self):
		return reverse('competitions:competitionproject_detail', args=[self.object.competitor.competition_project_id])
