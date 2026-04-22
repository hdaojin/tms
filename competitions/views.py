from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Q
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, DetailView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .forms import (
	CompetitionResultCreateForm,
	CompetitorCreateForm,
	ExpertCreateForm,
	MemberCreateForm,
	SkillPositionCreateForm,
)
from .models import Competition, CompetitionProject, CompetitionResult, Competitor, Expert, Member, SkillPosition
from .tables import CompetitionTable


def build_competition_project_url(name, competition_project_id, next_url=None):
	params = {'competition_project': competition_project_id}
	if next_url:
		params['next'] = next_url
	return f"{reverse(name)}?{urlencode(params)}"


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
		context['competition_projects'] = self.object.competition_projects.select_related(
			'project',
		).annotate(
			official_module_total=Count('competition_modules', distinct=True),
			competitor_total=Count('competitors', distinct=True),
			expert_total=Count('experts', distinct=True),
			result_total=Count('competitors__results', distinct=True),
		).order_by('project__name')
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

		context['official_modules'] = competition_project.competition_modules.all().order_by('sort_order', 'code', 'pk')
		context['competitors'] = competition_project.competitors.select_related('person__user', 'member').all().order_by('person__name', 'pk')
		context['experts'] = competition_project.experts.select_related('person__user', 'member').all().order_by('person__name')
		context['skill_positions'] = competition_project.skill_positions.select_related('person__user').all().order_by('position_name', 'person__name')
		context['results'] = CompetitionResult.objects.filter(
			competitor__competition_project=competition_project,
		).select_related(
			'competitor__member',
			'competitor__person__user',
		).order_by('rank', '-score_700', 'competitor__person__name')
		context['members'] = Member.objects.filter(
			Q(competitors__competition_project=competition_project)
			| Q(experts__competition_project=competition_project)
		).distinct().order_by('level', 'name')
		context['member_create_url'] = f"{reverse('competitions:member_create')}?{urlencode({'next': detail_url})}"
		context['competitor_create_url'] = build_competition_project_url(
			'competitions:competitor_create',
			competition_project.pk,
			detail_url,
		)
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


class MemberCreateView(CompetitionCreateViewMixin):
	model = Member
	form_class = MemberCreateForm
	permission_required = 'competitions.add_member'
	title = '新增代表队'
	title_icon = 'icon-[tabler--flag]' 
	submit_label = '保存代表队'
	success_message = '代表队已保存。'
	page_note = '竞赛主干信息由管理员在后台维护；前台只负责补录代表队及人员、成绩等业务信息。'

	def get_default_success_url(self):
		return reverse_lazy('competitions:member_create')


class CompetitorCreateView(CompetitionCreateViewMixin):
	model = Competitor
	form_class = CompetitorCreateForm
	permission_required = 'competitions.add_competitor'
	title = '新增选手'
	title_icon = 'icon-[tabler--user-plus]'
	submit_label = '保存选手'
	success_message = '选手信息已保存。'
	page_note = '请先选择具体赛项，系统会自动按赛事级别过滤可选代表队。'

	def get_default_success_url(self):
		return reverse('competitions:competitionproject_detail', args=[self.object.competition_project_id])


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
	page_note = '技能岗位人员仅补录本届赛事人员信息；竞赛类型、项目、模块等主干资料仍由管理员维护。'

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
