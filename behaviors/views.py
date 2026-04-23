from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django_tables2 import SingleTableView

from core.constants import CONDUCT_SEVERITY_MODERATE
from core.utils.mixins import TitleMixin
from .forms import ConductRecordForm
from .models import ConductItem, ConductRecord, ConductSummary, get_conduct_severity_choices_with_multiplier
from .tables import ConductRecordTable, ConductSummaryTable


class ConductRecordCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ConductRecord
    form_class = ConductRecordForm
    template_name = 'behaviors/conductrecord_create.html'
    success_url = reverse_lazy('behaviors:conductrecord_list')
    permission_required = 'behaviors.add_conduct_record'
    raise_exception = True
    title = "录入奖惩记录"
    title_icon = "icon-[tabler--plus]"

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)


class ConductRecordListView(TitleMixin, SingleTableView):
    model = ConductRecord
    table_class = ConductRecordTable
    template_name = 'behaviors/conductrecord_list.html'
    table_pagination = {"per_page": 20}
    title = "奖惩记录列表"
    title_icon = "icon-[tabler--list]"

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'student', 'item__category', 'recorded_by',
        )
        if not self.request.user.has_perm('behaviors.view_all_conduct_records'):
            qs = qs.filter(student=self.request.user)
        return qs


class ConductSummaryListView(TitleMixin, SingleTableView):
    model = ConductSummary
    table_class = ConductSummaryTable
    template_name = 'behaviors/conductsummary_list.html'
    table_pagination = {"per_page": 20}
    title = "奖惩汇总"
    title_icon = "icon-[tabler--chart-bar]"

    def get_queryset(self):
        qs = super().get_queryset().select_related('student')
        if not self.request.user.has_perm('behaviors.view_all_conduct_records'):
            qs = qs.filter(student=self.request.user)
        return qs


def item_choices_view(request):
    """HTMX endpoint: 根据选中的奖惩性质返回对应事项选项。"""
    nature = request.GET.get('nature')

    if not nature:
        return HttpResponse(
            '<option value="" selected>---------</option>',
        )

    items = ConductItem.objects.filter(
        is_active=True,
        category__nature=nature,
    ).select_related('category')

    options = ['<option value="" selected>---------</option>']
    for item in items:
        options.append(f'<option value="{item.pk}">{item}</option>')
    return HttpResponse(''.join(options))


def severity_choices_view(request):
    """HTMX endpoint: 根据选中的奖惩事项返回对应严重程度选项。"""
    item_id = request.GET.get('item')
    nature = None

    if item_id:
        item = ConductItem.objects.filter(
            pk=item_id,
        ).select_related('category').first()
        if item:
            nature = item.category.nature

    if nature is None:
        return HttpResponse(
            '<option value="" disabled selected>请先选择奖惩事项</option>',
        )

    choices = get_conduct_severity_choices_with_multiplier(nature)
    options = []
    for value, label in choices:
        selected = ' selected' if value == CONDUCT_SEVERITY_MODERATE else ''
        options.append(f'<option value="{value}"{selected}>{label}</option>')
    return HttpResponse(''.join(options))
