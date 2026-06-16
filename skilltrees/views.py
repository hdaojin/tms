from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.utils.mixins import TitleMixin

from .forms import SkillNodeForm, SkillNodeInlineCreateForm, SkillTreeForm
from .models import SkillNode, SkillTree


DETAIL_VIEW_LIST = "list"
DETAIL_VIEW_TREE = "tree"
DETAIL_VIEW_MODES = {DETAIL_VIEW_LIST, DETAIL_VIEW_TREE}


def get_detail_view_mode(value):
    if value in DETAIL_VIEW_MODES:
        return value
    return DETAIL_VIEW_LIST


def build_skill_node_tree_rows(nodes):
    children_by_parent = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    rows = []
    visited = set()

    def append_node(node, depth):
        if node.pk in visited:
            return
        visited.add(node.pk)
        rows.append(
            {
                "node": node,
                "depth": depth,
                "indent_rem": f"{depth * 1.5:.1f}",
            }
        )
        for child in children_by_parent.get(node.pk, []):
            append_node(child, depth + 1)

    for root in children_by_parent.get(None, []):
        append_node(root, 0)

    for node in nodes:
        if node.pk not in visited:
            append_node(node, 0)

    return rows


def _mapping_total_mark(mappings):
    return sum((mapping.aspect.max_mark for mapping in mappings), Decimal("0.00"))


def attach_aspect_coverage(nodes):
    from marking.models import MarkingAspectSkillNodeMap

    node_by_id = {node.pk: node for node in nodes}
    children_by_parent = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    direct_mappings = {node.pk: [] for node in nodes}
    mappings = (
        MarkingAspectSkillNodeMap.objects.filter(skill_node__in=nodes)
        .select_related(
            "skill_node",
            "aspect__scheme",
            "aspect__subcriterion",
        )
        .order_by(
            "-aspect__scheme__created_at",
            "aspect__sort_order",
            "aspect__code",
            "pk",
        )
    )
    for mapping in mappings:
        direct_mappings.setdefault(mapping.skill_node_id, []).append(mapping)

    descendant_skill_cache = {}

    def descendant_skill_ids(node):
        if node.pk in descendant_skill_cache:
            return descendant_skill_cache[node.pk]

        skill_ids = []
        for child in children_by_parent.get(node.pk, []):
            if child.node_type == SkillNode.NodeType.SKILL:
                skill_ids.append(child.pk)
            skill_ids.extend(descendant_skill_ids(child))
        descendant_skill_cache[node.pk] = skill_ids
        return skill_ids

    for node in nodes:
        direct = direct_mappings.get(node.pk, [])
        if node.node_type == SkillNode.NodeType.SKILL:
            coverage_mappings = list(direct)
            groups = []
            is_rollup = False
        else:
            coverage_mappings = []
            groups = []
            for skill_id in descendant_skill_ids(node):
                skill_node = node_by_id[skill_id]
                skill_mappings = direct_mappings.get(skill_id, [])
                if not skill_mappings:
                    continue
                coverage_mappings.extend(skill_mappings)
                groups.append(
                    {
                        "skill_node": skill_node,
                        "mappings": skill_mappings,
                        "count": len(skill_mappings),
                        "total_mark": _mapping_total_mark(skill_mappings),
                        "primary_count": sum(1 for mapping in skill_mappings if mapping.is_primary),
                    }
                )
            is_rollup = True

        node.direct_aspect_mappings = direct
        node.aspect_coverage_mappings = coverage_mappings
        node.aspect_coverage_groups = groups
        node.aspect_coverage_is_rollup = is_rollup
        node.aspect_coverage_count = len(coverage_mappings)
        node.aspect_coverage_total_mark = _mapping_total_mark(coverage_mappings)
        node.aspect_coverage_primary_count = sum(1 for mapping in coverage_mappings if mapping.is_primary)


def build_skill_tree_detail_context(skill_tree, view_mode, node_form=None, inline_success_message=""):
    view_mode = get_detail_view_mode(view_mode)
    tree_nodes = list(skill_tree.nodes.select_related("parent").order_by("sort_order", "code", "name", "pk"))
    attach_aspect_coverage(tree_nodes)
    return {
        "skill_tree": skill_tree,
        "nodes": sorted(tree_nodes, key=lambda node: (node.parent_id or 0, node.sort_order, node.code, node.name)),
        "tree_rows": build_skill_node_tree_rows(tree_nodes),
        "view_mode": view_mode,
        "node_form": node_form or SkillNodeInlineCreateForm(tree=skill_tree),
        "inline_success_message": inline_success_message,
    }


class SkillTreeListView(TitleMixin, LoginRequiredMixin, ListView):
    model = SkillTree
    template_name = "skilltrees/skilltree_list.html"
    context_object_name = "skill_trees"
    paginate_by = 20
    title = "技能树"
    title_icon = "icon-[tabler--hierarchy-3]"

    def get_queryset(self):
        return SkillTree.objects.select_related("module__project", "module__module_set").prefetch_related("nodes")


class SkillTreeCreateView(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = SkillTree
    form_class = SkillTreeForm
    template_name = "skilltrees/form.html"
    permission_required = "skilltrees.add_skilltree"
    raise_exception = True
    title = "新建技能树"
    title_icon = "icon-[tabler--plus]"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "技能树已创建。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("skilltrees:detail", args=[self.object.pk])


class SkillTreeDetailView(TitleMixin, LoginRequiredMixin, DetailView):
    model = SkillTree
    template_name = "skilltrees/skilltree_detail.html"
    context_object_name = "skill_tree"
    title = "{name}"
    title_icon = "icon-[tabler--hierarchy-3]"

    def get_queryset(self):
        return SkillTree.objects.select_related("module__project", "module__module_set").prefetch_related(
            "nodes__parent"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_skill_tree_detail_context(self.object, self.request.GET.get("view")))
        return context


class SkillNodeInlineCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "skilltrees.add_skillnode"
    raise_exception = True

    def dispatch(self, request, *args, **kwargs):
        self.skill_tree = get_object_or_404(
            SkillTree.objects.select_related("module__project", "module__module_set"),
            pk=kwargs["tree_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        view_mode = get_detail_view_mode(request.POST.get("view") or request.GET.get("view"))
        form = SkillNodeInlineCreateForm(request.POST, tree=self.skill_tree)
        if form.is_valid():
            form.save()
            if getattr(request, "htmx", False):
                context = build_skill_tree_detail_context(
                    self.skill_tree,
                    view_mode,
                    inline_success_message="技能节点已保存。",
                )
                content_context = {**context, "content_oob": True}
                return HttpResponse(
                    render_to_string("skilltrees/partials/node_inline_form.html", context, request=request)
                    + render_to_string("skilltrees/partials/detail_content.html", content_context, request=request)
                )
            messages.success(request, "技能节点已保存。")
            detail_url = reverse("skilltrees:detail", args=[self.skill_tree.pk])
            if view_mode == DETAIL_VIEW_TREE:
                detail_url = f"{detail_url}?view={DETAIL_VIEW_TREE}"
            return redirect(detail_url)

        context = build_skill_tree_detail_context(self.skill_tree, view_mode, node_form=form)
        if getattr(request, "htmx", False):
            return HttpResponse(render_to_string("skilltrees/partials/node_inline_form.html", context, request=request))

        context.update(
            {
                "object": self.skill_tree,
                "title": self.skill_tree.name,
                "title_icon": SkillTreeDetailView.title_icon,
            }
        )
        return render(request, "skilltrees/skilltree_detail.html", context, status=400)


class SkillNodeCreateView(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = SkillNode
    form_class = SkillNodeForm
    template_name = "skilltrees/form.html"
    permission_required = "skilltrees.add_skillnode"
    raise_exception = True
    title = "新增技能节点"
    title_icon = "icon-[tabler--plus]"

    def dispatch(self, request, *args, **kwargs):
        self.skill_tree = get_object_or_404(SkillTree, pk=kwargs["tree_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tree"] = self.skill_tree
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "技能节点已保存。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("skilltrees:detail", args=[self.skill_tree.pk])


class SkillNodeUpdateView(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = SkillNode
    form_class = SkillNodeForm
    template_name = "skilltrees/form.html"
    permission_required = "skilltrees.change_skillnode"
    raise_exception = True
    title = "编辑技能节点"
    title_icon = "icon-[tabler--edit]"

    def get_queryset(self):
        return SkillNode.objects.select_related("tree")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tree"] = self.object.tree
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "技能节点已更新。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("skilltrees:detail", args=[self.object.tree_id])


class SkillNodeDeactivateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "skilltrees.change_skillnode"
    raise_exception = True

    def post(self, request, pk):
        node = get_object_or_404(SkillNode, pk=pk)
        node.is_active = False
        node.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"技能节点“{node.name}”已停用。")
        return redirect("skilltrees:detail", pk=node.tree_id)
