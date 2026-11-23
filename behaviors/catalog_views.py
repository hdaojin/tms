from functools import cached_property

from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe
from django_tables2 import SingleTableView

from core.utils.breadcrumbs import breadcrumb_link, build_breadcrumbs
from core.utils.listing import FilterableListMixin, ListFilterSpec
from core.utils.mixins import TitleMixin

from .cycle_forms import CategoryForm, ItemForm, SeverityForm, SeverityRuleForm
from .models import ConductCategory, ConductItem, ConductNature, ConductSeverity, ConductSeverityRule, format_conduct_score
from .permissions import GLOBAL_CATALOG_PERMISSION
from .tables import CatalogCategoryTable, CatalogItemTable, SeverityRateTable, SeverityTable

require_catalog = permission_required(GLOBAL_CATALOG_PERMISSION, raise_exception=True)


def category_parent():
    return breadcrumb_link('奖惩分类', 'behaviors:catalog_categories')


def item_parent(category):
    return breadcrumb_link(category.name, 'behaviors:catalog_items', args=[category.pk])


def rate_parent():
    return breadcrumb_link('程度与倍率', 'behaviors:catalog_rates')


class CatalogList(FilterableListMixin, PermissionRequiredMixin, TitleMixin, SingleTableView):
    permission_required = GLOBAL_CATALOG_PERMISSION
    raise_exception = True
    template_name = 'behaviors/conductrecord_list.html'
    list_filter_htmx = False
    table_pagination = {'per_page': 25}
    search_fields = ('name', 'code')
    list_filter_specs = (
        ListFilterSpec('q', '搜索', 'search', placeholder='名称或代码'),
        ListFilterSpec('active', '状态', 'select', lookup='is_active', choices=(('True', '启用'), ('False', '停用'))),
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_actions'] = self.get_page_actions()
        return context


class CategoryList(CatalogList):
    model = ConductCategory
    table_class = CatalogCategoryTable
    title = '奖惩分类'
    list_filter_specs = (
        *CatalogList.list_filter_specs,
        ListFilterSpec('nature', '性质', 'select', lookup='nature', choices=ConductNature.choices),
    )

    def get_page_actions(self):
        return [{'label': '新增分类', 'href': reverse('behaviors:category_new'), 'variant_class': 'btn-primary'}]


class ItemList(CatalogList):
    model = ConductItem
    table_class = CatalogItemTable

    @cached_property
    def category(self):
        return get_object_or_404(ConductCategory, pk=self.kwargs['category_pk'])

    def get_title(self):
        return f'{self.category.name} · 奖惩事项'

    def get_breadcrumb_parents(self):
        return [category_parent()]

    def get_base_queryset(self):
        return ConductItem.objects.filter(category=self.category)

    def get_page_actions(self):
        return [
            {'label': '新增事项', 'href': reverse('behaviors:item_new', args=[self.category.pk]), 'variant_class': 'btn-primary'},
            {'label': '分类详情', 'href': reverse('behaviors:category_detail', args=[self.category.pk])},
        ]


class RateList(CatalogList):
    model = ConductSeverityRule
    table_class = SeverityRateTable
    title = '程度与倍率'
    search_fields = ('label', 'severity__name', 'severity__code')
    list_filter_specs = (
        ListFilterSpec('q', '搜索', 'search', placeholder='程度名称、显示名称或代码'),
        ListFilterSpec('nature', '性质', 'select', lookup='nature', choices=ConductNature.choices),
    )

    def get_base_queryset(self):
        return ConductSeverityRule.objects.select_related('severity')

    def get_page_actions(self):
        return [
            {'label': '新增倍率', 'href': reverse('behaviors:rate_new'), 'variant_class': 'btn-primary'},
            {'label': '管理程度', 'href': reverse('behaviors:severity_list')},
        ]


class SeverityList(CatalogList):
    model = ConductSeverity
    title = '奖惩程度'
    table_class = SeverityTable

    def get_breadcrumb_parents(self):
        return [rate_parent()]

    def get_page_actions(self):
        return [{'label': '新增程度', 'href': reverse('behaviors:severity_new'), 'variant_class': 'btn-primary'}]


def catalog_page(request, title, parents, **context):
    return render(request, 'behaviors/catalog_object.html', {
        'title': title, 'breadcrumbs': build_breadcrumbs(request, title, parents), **context,
    })


@require_safe
@require_catalog
def category_detail(request, pk):
    category = get_object_or_404(ConductCategory, pk=pk)
    return catalog_page(
        request, category.name, [category_parent()], obj=category,
        fields=[
            ('性质', category.nature_label), ('分类代码', category.code), ('分类名称', category.name),
            ('说明', category.description), ('排序', category.order), ('状态', '启用' if category.is_active else '停用'),
        ],
        page_actions=[
            {'label': '查看事项', 'href': reverse('behaviors:catalog_items', args=[pk])},
            {'label': '编辑分类', 'href': reverse('behaviors:category_edit', args=[pk]), 'variant_class': 'btn-primary'},
        ],
    )


@require_safe
@require_catalog
def item_detail(request, category_pk, pk):
    item = get_object_or_404(ConductItem.objects.select_related('category'), pk=pk, category_id=category_pk)
    return catalog_page(
        request, item.name, [category_parent(), item_parent(item.category)], obj=item,
        fields=[
            ('所属分类', item.category.name), ('事项代码', item.code), ('事项名称', item.name),
            ('基准分', format_conduct_score(item.default_score)), ('说明', item.description),
            ('状态', '启用' if item.is_active else '停用'),
        ],
        page_actions=[
            {'label': '编辑事项', 'href': reverse('behaviors:item_edit', args=[category_pk, pk]), 'variant_class': 'btn-primary'},
        ],
    )


def save_catalog_form(form, actor):
    obj = form.save(commit=False)
    if isinstance(obj, (ConductCategory, ConductItem, ConductSeverityRule)):
        obj.updated_by = actor
        if not obj.pk:
            obj.created_by = actor
    with transaction.atomic():
        if isinstance(obj, ConductSeverityRule):
            obj.is_default = form.cleaned_data['set_default']
            if obj.is_default:
                ConductSeverityRule.objects.filter(nature=obj.nature, is_default=True).exclude(pk=obj.pk).update(
                    is_default=False, updated_by=actor, updated_at=timezone.now(),
                )
        obj.save()
    return obj


@require_http_methods(['GET', 'POST'])
@require_catalog
@transaction.atomic
def catalog_edit(request, kind, pk=None, category_pk=None):
    parents = [category_parent()]
    kwargs = {}
    lookup = {}
    if kind == 'category':
        model, form_class, destination = ConductCategory, CategoryForm, 'behaviors:category_detail'
    elif kind == 'item':
        category = get_object_or_404(ConductCategory, pk=category_pk)
        parents.append(item_parent(category))
        model, form_class, destination = ConductItem, ItemForm, 'behaviors:item_detail'
        kwargs = lookup = {'category': category}
    else:
        parents = [rate_parent()]
        if kind == 'severity':
            model, form_class, destination = ConductSeverity, SeverityForm, 'behaviors:severity_list'
        else:
            model, form_class, destination = ConductSeverityRule, SeverityRuleForm, 'behaviors:catalog_rates'

    if request.method == 'POST' and kind in {'severity', 'rate'}:
        list(ConductSeverity.objects.order_by('pk').select_for_update().values_list('pk', flat=True))
    objects = model.objects.select_for_update() if request.method == 'POST' else model.objects.all()
    instance = get_object_or_404(objects, pk=pk, **lookup) if pk else model(**lookup)
    form = form_class(request.POST if request.method == 'POST' else None, instance=instance, **kwargs)
    if request.method == 'POST' and form.is_valid():
        try:
            obj = save_catalog_form(form, request.user)
        except IntegrityError:
            form.add_error(None, '代码、名称或默认档已存在，请核对后重试。')
        else:
            args = {'category': [obj.pk], 'item': [category_pk, obj.pk]}.get(kind, [])
            return redirect(destination, *args)
    return catalog_page(request, f'{"编辑" if pk else "新增"}{model._meta.verbose_name}', parents, form=form, obj=instance)


@require_safe
@require_catalog
def old_catalog(request, pk, kind=None, object_pk=None):
    if kind == 'category' and ConductCategory.objects.filter(pk=object_pk).exists():
        return redirect('behaviors:catalog_items', category_pk=object_pk)
    if kind == 'item':
        item = ConductItem.objects.filter(pk=object_pk).first()
        if item:
            return redirect('behaviors:item_detail', category_pk=item.category_id, pk=item.pk)
    return redirect('behaviors:catalog_categories')
