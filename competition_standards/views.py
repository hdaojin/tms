from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .models import TrainingCycle
from .tables import TrainingCycleTable


class TrainingCycleListView(TitleMixin, LoginRequiredMixin, SingleTableView):
	model = TrainingCycle
	table_class = TrainingCycleTable
	template_name = 'competition_standards/trainingcycle_list.html'
	paginate_by = 20
	title = '训练周期'
	title_icon = 'icon-[tabler--calendar]'

	def get_queryset(self):
		return (
			super()
			.get_queryset()
			.select_related(
				'project__competition_type',
				'module_set',
			)
		)


class TrainingCycleDetailView(TitleMixin, LoginRequiredMixin, DetailView):
	model = TrainingCycle
	template_name = 'competition_standards/trainingcycle_detail.html'
	context_object_name = 'training_cycle'
	title = '{name}'
	title_icon = 'icon-[tabler--calendar]'

	def get_queryset(self):
		return (
			super()
			.get_queryset()
			.select_related(
				'project__competition_type',
				'module_set',
			)
			.prefetch_related('training_logs', 'assessments')
		)
