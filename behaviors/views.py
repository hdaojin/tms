from pathlib import Path

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.html import escape
from django.views.generic import CreateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin
from .forms import ConductRecordForm
from .models import (
    ConductItem,
    ConductNature,
    ConductRecord,
    ConductSummary,
    get_conduct_severity_choices_with_multiplier,
    get_default_conduct_severity,
)
from .permissions import ADD_CONDUCT_RECORD_PERMISSION
from .selectors import get_conduct_record_list_queryset, get_conduct_summary_list_queryset
from .services import prepare_conduct_record_for_save
from .tables import ConductRecordTable, ConductSummaryTable


class ConductRecordCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ConductRecord
    form_class = ConductRecordForm
    template_name = 'behaviors/conductrecord_create.html'
    success_url = reverse_lazy('behaviors:conductrecord_list')
    permission_required = ADD_CONDUCT_RECORD_PERMISSION
    raise_exception = True
    title = "录入奖惩记录"
    title_icon = "icon-[tabler--plus]"

    def form_valid(self, form):
        prepare_conduct_record_for_save(form.instance, actor=self.request.user, change=False)
        return super().form_valid(form)


class ConductRecordListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = ConductRecord
    table_class = ConductRecordTable
    template_name = 'behaviors/conductrecord_list.html'
    table_pagination = {"per_page": 20}
    title = "奖惩记录列表"
    title_icon = "icon-[tabler--list]"
    permission_required = "behaviors.view_conductrecord"

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'student', 'item__category', 'severity', 'recorded_by',
        )
        return get_conduct_record_list_queryset(qs, self.request.user)


class ConductSummaryListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = ConductSummary
    table_class = ConductSummaryTable
    template_name = 'behaviors/conductsummary_list.html'
    table_pagination = {"per_page": 20}
    title = "奖惩汇总"
    title_icon = "icon-[tabler--chart-bar]"
    permission_required = "behaviors.view_conductsummary"

    def get_queryset(self):
        qs = super().get_queryset().select_related('student')
        return get_conduct_summary_list_queryset(qs, self.request.user)


@permission_required("behaviors.view_conductrecord", raise_exception=True)
def conduct_attachment_view(request, pk):
    record = get_object_or_404(
        get_conduct_record_list_queryset(
            ConductRecord.objects.select_related("student", "recorded_by"),
            request.user,
        ),
        pk=pk,
    )
    if not record.attachment:
        raise Http404
    return FileResponse(
        record.attachment.open("rb"),
        as_attachment=True,
        filename=Path(record.attachment.name).name,
    )


@permission_required("behaviors.add_conduct_record", raise_exception=True)
def item_choices_view(request):
    """HTMX endpoint: 根据选中的奖惩性质返回对应事项选项。"""
    nature = request.GET.get('nature')

    if nature not in ConductNature.values:
        return HttpResponse(
            '<option value="" selected>---------</option>',
        )

    items = ConductItem.objects.filter(
        is_active=True,
        category__is_active=True,
        category__nature=nature,
    ).select_related('category')

    options = ['<option value="" selected>---------</option>']
    for item in items:
        options.append(f'<option value="{item.pk}">{escape(item)}</option>')
    return HttpResponse(''.join(options))


@permission_required("behaviors.add_conduct_record", raise_exception=True)
def severity_choices_view(request):
    """HTMX endpoint: 根据选中的奖惩事项返回对应严重程度选项。"""
    item_id = request.GET.get('item')
    nature = None

    if item_id:
        item = ConductItem.objects.filter(
            pk=item_id,
            is_active=True,
            category__is_active=True,
            category__nature__in=ConductNature.values,
        ).select_related('category').first()
        if item:
            nature = item.category.nature

    if nature is None:
        return HttpResponse(
            '<option value="" disabled selected>请先选择奖惩事项</option>',
        )

    choices = get_conduct_severity_choices_with_multiplier(nature)
    default_rule = get_default_conduct_severity(nature)
    default_code = default_rule.severity.code if default_rule is not None else None
    options = []
    if not choices:
        return HttpResponse(
            '<option value="" disabled selected>当前性质未配置严重程度规则</option>',
        )
    if default_code is None:
        options.append('<option value="" selected>请选择程度（未配置默认项）</option>')
    for value, label in choices:
        selected = ' selected' if value == default_code else ''
        options.append(f'<option value="{escape(value)}"{selected}>{escape(label)}</option>')
    return HttpResponse(''.join(options))
