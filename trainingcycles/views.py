from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .models import TrainingCycle
from .tables import TrainingCycleTable


class TrainingCycleListView(TitleMixin, LoginRequiredMixin, SingleTableView):
    model = TrainingCycle
    table_class = TrainingCycleTable
    template_name = 'trainingcycles/trainingcycle_list.html'
    paginate_by = 20
    title = '备赛周期'
    title_icon = 'icon-[tabler--calendar]'

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                'project__competition_type',
                'module_set',
                'primary_competition_project__competition',
                'primary_competition_project__project',
                'reference_competition_project__competition',
                'reference_competition_project__project',
            )
        )


class TrainingCycleDetailView(TitleMixin, LoginRequiredMixin, DetailView):
    model = TrainingCycle
    template_name = 'trainingcycles/trainingcycle_detail.html'
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
                'primary_competition_project__competition',
                'primary_competition_project__project',
                'reference_competition_project__competition',
                'reference_competition_project__project',
            )
            .prefetch_related('training_logs', 'assessments')
        )

