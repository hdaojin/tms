import json
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import FormView
from django_tables2 import SingleTableView

from competition_standards.models import StandardModule
from competitions.models import CompetitionProject
from core.utils.mixins import TitleMixin
from .forms import ExamPointEntryForm, SkillFilterForm
from .models import ExamPoint, Skill, Topic
from .tables import SkillTable


DEPENDENCY_FORM_KEYS = {
	'competition_project',
	'module',
	'topic_mode',
	'existing_topic',
	'existing_skills',
}


def _build_dependency_form(query_params):
	filtered_data = query_params.copy()
	for key in list(filtered_data.keys()):
		if key not in DEPENDENCY_FORM_KEYS:
			del filtered_data[key]
	return ExamPointEntryForm(data=filtered_data or None)


class SkillListView(TitleMixin, LoginRequiredMixin, SingleTableView):
	model = Skill
	table_class = SkillTable
	template_name = 'skills/skill_list.html'
	table_pagination = {"per_page": 20}
	title = "技能点列表"
	title_icon = "icon-[tabler--list-search]"

	def get_filter_form(self):
		if not hasattr(self, '_filter_form'):
			self._filter_form = SkillFilterForm(self.request.GET or None)
		return self._filter_form

	def get_queryset(self):
		queryset = (
			super()
			.get_queryset()
			.select_related('topic__module__project')
			.annotate(exam_point_count=Count('exam_points', distinct=True))
		)
		form = self.get_filter_form()
		if form.is_valid():
			module = form.cleaned_data.get('module')
			keyword = (form.cleaned_data.get('keyword') or '').strip()

			if module is not None:
				queryset = queryset.filter(topic__module=module)
			if keyword:
				queryset = queryset.filter(
					Q(topic__name__icontains=keyword)
					| Q(name__icontains=keyword)
					| Q(description__icontains=keyword)
				)

		return queryset.order_by('topic__module__project__name', 'topic__module__code', 'topic__name', 'name')

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['filter_form'] = self.get_filter_form()
		context['filter_active'] = bool(self.request.GET)
		return context


class ExamPointCreateView(TitleMixin, LoginRequiredMixin, FormView):
	form_class = ExamPointEntryForm
	template_name = 'skills/exam_point_create.html'
	title = '录入考点'
	title_icon = 'icon-[tabler--plus]'

	def get_initial(self):
		initial = super().get_initial()
		for key in ('competition_project', 'module', 'topic_mode', 'existing_topic'):
			value = self.request.GET.get(key)
			if value:
				initial[key] = value
		return initial

	def get_new_skill_rows(self, form):
		if form.is_bound:
			rows = form.data.getlist('new_skill_names')
			return rows or ['']
		return ['']

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['new_skill_rows_json'] = json.dumps(
			self.get_new_skill_rows(context['form']),
			ensure_ascii=False,
		)
		return context

	def form_valid(self, form):
		self.object = form.save()
		summary = form.save_summary
		self.saved_topic = summary.get('topic')
		self.saved_module = summary['module']
		summary = form.save_summary
		message = f'考点“{self.object.name}”已录入，共关联 {summary["skill_count"]} 个技能点。'
		if self.saved_topic is not None and (summary['created_skill_count'] or summary['reused_skill_count']):
			topic_action = '新建' if summary['topic_created'] else '复用'
			message += f'{topic_action}专题“{self.saved_topic.name}”。'
		if summary['created_skill_count'] or summary['reused_skill_count']:
			message += (
				f'其中新增 {summary["created_skill_count"]} 个，'
				f'复用 {summary["reused_skill_count"]} 个。'
			)
		messages.success(self.request, message)
		return super().form_valid(form)

	def get_success_url(self):
		params = {
			'competition_project': self.object.competition_project_id,
			'module': self.saved_module.pk,
			'topic_mode': 'existing',
		}
		if self.saved_topic is not None:
			params['existing_topic'] = self.saved_topic.pk
		params = urlencode(params)
		return f'{reverse("skills:exam_point_create")}?{params}'


@login_required
def exam_point_dependency_fields(request):
	form = _build_dependency_form(request.GET)
	return render(
		request,
		'skills/partials/exam_point_dependency_fields.html',
		{'form': form},
	)


@login_required
def exam_point_topic_suggestions(request):
	query = (request.GET.get('new_topic_name') or '').strip()
	module = StandardModule.objects.current().filter(pk=request.GET.get('module')).select_related('project', 'module_set').first()
	suggestions = Topic.objects.none()
	if module is not None and query:
		suggestions = Topic.objects.filter(module=module, name__icontains=query).order_by('name')[:6]
	return render(
		request,
		'skills/partials/topic_suggestions.html',
		{
			'module': module,
			'query': query,
			'suggestions': suggestions,
		},
	)


@login_required
def exam_point_name_suggestions(request):
	query = (request.GET.get('name') or '').strip()
	competition_project = CompetitionProject.objects.filter(pk=request.GET.get('competition_project')).select_related(
		'competition',
		'project',
	).first()
	suggestions = ExamPoint.objects.none()
	if competition_project is not None and query:
		suggestions = (
			ExamPoint.objects.filter(competition_project=competition_project, name__icontains=query)
			.prefetch_related('skills__topic__module')
			.order_by('name')[:6]
		)
	return render(
		request,
		'skills/partials/exam_point_suggestions.html',
		{
			'competition_project': competition_project,
			'query': query,
			'suggestions': suggestions,
		},
	)

