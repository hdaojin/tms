from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_safe
from django_tables2 import SingleTableView

from core.utils.listing import FilterableListMixin, ListFilterSpec
from core.utils.mixins import TitleMixin

from .cycle_services import cycle_scope
from .models import ConductNature, ConductRecord
from .selectors import (
    can_view_records, can_view_summaries, ledger_cycles, legacy_permission, search_students, summarize_records,
    visible_records,
)
from .tables import ConductRecordTable, ConductSummaryTable


class LedgerList(FilterableListMixin, TitleMixin, SingleTableView):
    template_name = 'behaviors/conductrecord_list.html'
    table_pagination = {'per_page': 25}
    list_filter_htmx = False
    summary = False

    def dispatch(self, request, *args, **kwargs):
        access = can_view_summaries if self.summary else can_view_records
        if not access(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_list_filter_specs(self):
        cycles = ledger_cycles(self.request.user, summary=self.summary)
        choices = [(cycle.pk, str(cycle)) for cycle in cycles]
        if legacy_permission(self.request.user, summary=self.summary):
            choices.append(('unassigned', '未关联周期'))
        return (
            ListFilterSpec('q', '学员', 'search', placeholder='学员姓名、全拼或首字母'),
            ListFilterSpec('cycle', '训练周期', 'select', choices=choices, empty_label='全部周期'),
            *self.list_filter_specs,
        )

    def get_base_queryset(self):
        return visible_records(self.request.user, summary=self.summary)

    def apply_search(self, queryset):
        query = self.get_search_query()
        return search_students(queryset, query) if query else queryset

    def apply_custom_filters(self, queryset):
        spec = next(spec for spec in self.resolved_list_filter_specs if spec.name == 'cycle')
        cycle = self.get_filter_value(spec)
        if not cycle:
            return queryset.none() if self.request.GET.get('cycle') else queryset
        if cycle == 'unassigned':
            return queryset.filter(cycle__isnull=True)
        return queryset.filter(cycle_id=cycle)


class ConductRecordListView(LedgerList):
    table_class = ConductRecordTable
    title = '奖惩记录'
    title_icon = 'icon-[tabler--list]'
    list_filter_status_param = 'status'
    list_filter_specs = (
        ListFilterSpec('status', '状态', 'select', lookup='status', choices=ConductRecord.Status.choices, empty_label='全部状态'),
        ListFilterSpec('nature', '奖惩性质', 'select', lookup='frozen_nature', choices=ConductNature.choices),
        ListFilterSpec('date_from', '起始日期', 'date', advanced=True),
        ListFilterSpec('date_to', '结束日期', 'date', advanced=True),
    )

    def get_base_queryset(self):
        return super().get_base_queryset().select_related('cycle', 'student')

    def apply_custom_filters(self, queryset):
        queryset = super().apply_custom_filters(queryset)
        for key, lookup in (('date_from', 'occurred_date__gte'), ('date_to', 'occurred_date__lte')):
            if raw := self.request.GET.get(key):
                try:
                    date = parse_date(raw)
                except ValueError:
                    return queryset.none()
                if date is None:
                    return queryset.none()
                queryset = queryset.filter(**{lookup: date})
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycles = cycle_scope(self.request.user, 'enter')
        if cycles.exists():
            context['page_actions'] = [
                {'label': '录入奖惩', 'href': reverse('behaviors:conductrecord_create'), 'variant_class': 'btn-primary'},
            ]
        return context


class ConductSummaryListView(LedgerList):
    table_class = ConductSummaryTable
    title = '积分汇总'
    title_icon = 'icon-[tabler--chart-bar]'
    summary = True

    def get_queryset(self):
        return summarize_records(super().get_queryset())


def ledger_record(user, **lookup):
    return get_object_or_404(
        visible_records(user).select_related('cycle', 'student', 'rule__policy_item__policy', 'rule__policy_item__item',
                                             'recorded_by', 'reviewed_by', 'voided_by'),
        **lookup,
    )


def find_old_cycle_record(user, cycle_pk, pk):
    return ledger_record(user, cycle_id=cycle_pk, source_cycle_record_id=pk)


@require_safe
def conduct_attachment_view(request, pk):
    if not can_view_records(request.user):
        raise PermissionDenied
    record = ledger_record(request.user, pk=pk)
    if not record.attachment:
        raise Http404
    try:
        stream = record.attachment.open('rb')
    except FileNotFoundError as exc:
        raise Http404 from exc
    return FileResponse(stream, as_attachment=True, filename=Path(record.attachment.name).name)


@require_safe
def old_cycle_attachment(request, pk, record_pk):
    record = find_old_cycle_record(request.user, pk, record_pk)
    return redirect('behaviors:conduct_attachment', record.pk)
