import json

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Exists, OuterRef, Sum
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin
from core.utils.listing import FilterableListMixin, ListFilterSpec

from .forms import (
    SkillForm,
    SkillProjectForm,
    SkillTreeAttachExistingForm,
    SkillTreeMoveForm,
    SkillTreeQuickAddForm,
    SkillTreeRemoveForm,
    SkillTreeVersionForm,
    SkillWSOSMapNoteForm,
    TechnicalDomainForm,
    WSOSSectionForm,
    WSOSVersionForm,
)
from .models import (
    Skill,
    SkillProject,
    SkillTreeNode,
    SkillTreeVersion,
    SkillWSOSMap,
    TechnicalDomain,
    WSOSSection,
    WSOSVersion,
)
from .selectors import (
    can_manage_domain,
    can_manage_skill,
    current_skill_tree_for,
    current_wsos_for,
    is_project_admin,
    manageable_domains_for,
    manageable_skills_for,
    project_domains_for_view,
    skill_assessment_history,
    skill_assessment_performance,
    skill_tree_structure,
    search_skill_tree_nodes,
    skill_training_investment,
    unmounted_primary_skills_for_tree,
    visible_skills_for,
    wsos_skill_candidates,
    decorate_skill_tree_paths,
)
from .services import (
    add_skill_alias,
    attach_existing_skill_to_tree,
    create_detailed_skill_in_tree,
    create_skill_in_tree,
    delete_wsos_section,
    find_skill_candidates,
    map_skill_to_wsos_section,
    move_skill_tree_node,
    remove_skill_tree_node,
    reorder_skill_tree_node,
    save_skill,
    set_current_skill_tree_version,
    unmap_skill_from_wsos_section,
    update_skill_wsos_map_note,
)
from .tables import (
    SkillProjectTable,
    SkillTreeNodeTable,
    SkillTreeVersionTable,
    WSOSVersionTable,
)


def _decorate_candidate_permissions(user, candidates):
    visible_ids = set(
        visible_skills_for(user).filter(pk__in=[item.pk for item in candidates]).values_list("pk", flat=True)
    )
    for candidate in candidates:
        candidate.can_register_alias = can_manage_skill(user, candidate)
        candidate.can_view_detail = candidate.pk in visible_ids
    return candidates


class StandardListMixin:
    template_name = "standards/object_list.html"
    create_url_name = None
    create_label = "新增"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url_name"] = self.create_url_name
        context["create_label"] = self.create_label
        return context


class StandardCreateMixin:
    template_name = "common/form.html"
    success_url_name = None

    def form_valid(self, form):
        if hasattr(form.instance, "created_by_id") and not form.instance.created_by_id:
            form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(self.success_url_name, args=[self.object.pk])


class SkillProjectListView(StandardListMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = SkillProject
    table_class = SkillProjectTable
    title = "技能项目"
    title_icon = "icon-[tabler--schema]"
    permission_required = "standards.view_skillproject"
    create_url_name = "standards:project_create"
    create_label = "新增技能项目"


class SkillProjectDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = SkillProject
    context_object_name = "project"
    template_name = "standards/project_detail.html"
    title = "{name}"
    permission_required = "standards.view_skillproject"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        domains = project_domains_for_view(
            project=self.object,
            user=self.request.user,
        )
        can_view_tree = self.request.user.has_perm("standards.view_skilltreeversion")
        for domain in domains:
            domain.can_view_tree = can_view_tree
        context.update(
            current_wsos=current_wsos_for(self.object),
            domains=domains,
            can_view_domain_management=self.request.user.has_perm("standards.view_technicaldomain"),
        )
        actions = []
        if self.request.user.has_perm("standards.change_skillproject"):
            actions.append(
                {
                    "label": "编辑项目",
                    "href": reverse("standards:project_edit", args=[self.object.pk]),
                    "icon": "icon-[tabler--edit]",
                    "variant_class": "btn-outline",
                    "size_class": "btn-sm",
                }
            )
        if self.request.user.has_perm("standards.add_technicaldomain"):
            actions.append(
                {
                    "label": "新增技术领域",
                    "href": reverse("standards:domain_create", args=[self.object.pk]),
                    "icon": "icon-[tabler--plus]",
                    "variant_class": "btn-primary",
                    "size_class": "btn-sm",
                }
            )
        if actions:
            context["page_actions"] = actions
        return context


class SkillProjectCreateView(StandardCreateMixin, TitleMixin, PermissionRequiredMixin, CreateView):
    model = SkillProject
    form_class = SkillProjectForm
    title = "新增技能项目"
    permission_required = "standards.add_skillproject"
    success_url_name = "standards:project_detail"


class SkillProjectUpdateView(SkillProjectCreateView, UpdateView):
    title = "编辑技能项目"
    permission_required = "standards.change_skillproject"


class TechnicalDomainCreateView(StandardCreateMixin, TitleMixin, PermissionRequiredMixin, CreateView):
    model = TechnicalDomain
    form_class = TechnicalDomainForm
    title = "新增技术领域"
    permission_required = "standards.add_technicaldomain"

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(SkillProject, pk=kwargs["project_pk"], is_active=True)
        return super().dispatch(request, *args, **kwargs)

    def get_title(self):
        return f"新增{self.project.name}技术领域"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.setdefault("initial", {})["skill_project"] = self.project
        if kwargs.get("data") is not None:
            kwargs["data"] = kwargs["data"].copy()
            kwargs["data"]["skill_project"] = self.project.pk
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["skill_project"].widget = forms.HiddenInput()
        return form

    def form_valid(self, form):
        form.instance.skill_project = self.project
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "standards:current_domain_tree",
            kwargs={"project_pk": self.project.pk, "domain_pk": self.object.pk},
        )


class TechnicalDomainUpdateView(TechnicalDomainCreateView, UpdateView):
    title = "编辑技术领域"
    permission_required = "standards.change_technicaldomain"
    pk_url_kwarg = "domain_pk"

    def get_title(self):
        return f"编辑{self.project.name}技术领域"

    def get_queryset(self):
        return manageable_domains_for(self.request.user, self.project).filter(pk=self.kwargs["domain_pk"])


class CurrentSkillTreeEntryView(TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "standards/skill_project_select.html"
    title = "选择技能项目"
    title_icon = "icon-[tabler--hierarchy-3]"
    permission_required = "standards.view_skillproject"

    def get(self, request, *args, **kwargs):
        projects = SkillProject.objects.filter(is_active=True)
        project = projects.filter(is_default=True).first()
        if project is None and projects.count() == 1:
            project = projects.first()
        if project is not None:
            return redirect("standards:project_detail", pk=project.pk)
        if not projects.exists():
            raise Http404
        self.projects = projects
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["projects"] = self.projects
        return context


class SkillDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = Skill
    context_object_name = "skill"
    template_name = "standards/skill_detail.html"
    title = "{name}"
    permission_required = "standards.view_skill"

    def get_queryset(self):
        return (
            visible_skills_for(self.request.user)
            .select_related("skill_project", "primary_domain")
            .prefetch_related("related_domains", "terms", "tree_nodes", "wsos_mappings")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_edit_skill"] = can_manage_skill(self.request.user, self.object)
        context["assessment_history"] = skill_assessment_history(self.object)
        context["training_investment"] = skill_training_investment(self.object)
        context["assessment_performance"] = skill_assessment_performance(self.object)
        return context


class SkillUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = Skill
    form_class = SkillForm
    template_name = "common/form.html"
    title = "编辑技能"
    permission_required = "standards.change_skill"

    def get_queryset(self):
        return manageable_skills_for(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        skill = form.save(commit=False)
        try:
            save_skill(
                skill=skill,
                aliases=form._split_text(form.cleaned_data.get("aliases_text")),
                related_domains=form.cleaned_data.get("related_domains", ()),
                preserve_old_name=form.cleaned_data.get("preserve_old_name", False),
                old_name=form.old_name,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)
        self.object = skill
        return redirect("standards:skill_detail", pk=skill.pk)


def skill_candidates(request):
    if not request.user.has_perm("standards.add_skill"):
        raise PermissionDenied
    project_id = request.GET.get("skill_project")
    if not project_id:
        return render(request, "standards/partials/skill_candidates.html", {})
    project = get_object_or_404(SkillProject, pk=project_id, is_active=True)
    if not manageable_domains_for(request.user, project).exists() and not is_project_admin(request.user):
        raise Http404
    query = request.GET.get("name", "")
    candidates = _decorate_candidate_permissions(
        request.user,
        find_skill_candidates(skill_project=project, query=query),
    )
    return render(
        request,
        "standards/partials/skill_candidates.html",
        {
            "candidates": candidates,
            "candidate_query": query,
            "has_high_similarity": any(
                candidate.candidate_high_similarity and not candidate.candidate_exact for candidate in candidates
            ),
        },
    )


def skill_domain_fields(request):
    if not request.user.has_perm("standards.add_skill"):
        raise PermissionDenied
    project_id = request.GET.get("skill_project")
    form = SkillForm(user=request.user, initial={"skill_project": project_id})
    if not project_id:
        form.fields["primary_domain"].queryset = TechnicalDomain.objects.none()
        form.fields["related_domains"].queryset = TechnicalDomain.objects.none()
    return render(request, "standards/partials/skill_domain_fields.html", {"skill_form": form})


@require_POST
def skill_alias_add(request, pk):
    if not request.user.has_perm("standards.change_skill"):
        raise PermissionDenied
    skill = get_object_or_404(Skill, pk=pk)
    if not can_manage_skill(request.user, skill):
        raise Http404
    try:
        _, created = add_skill_alias(skill=skill, term=request.POST.get("term", ""))
    except ValidationError as exc:
        return render(
            request,
            "standards/partials/skill_alias_result.html",
            {"alias_error": exc.message},
        )
    response = render(
        request,
        "standards/partials/skill_alias_result.html",
        {"alias_added": created, "skill": skill, "term": request.POST.get("term", "").strip()},
    )
    response.headers["HX-Trigger"] = f'{{"skillAliasAdded":{{"skillId":{skill.pk}}}}}'
    return response


class SkillTreeVersionListView(
    FilterableListMixin,
    StandardListMixin,
    TitleMixin,
    PermissionRequiredMixin,
    SingleTableView,
):
    model = SkillTreeVersion
    table_class = SkillTreeVersionTable
    title = "技能树版本"
    permission_required = "standards.view_skilltreeversion"
    list_filter_specs = (
        ListFilterSpec("project", "技能项目", "select"),
        ListFilterSpec("domain", "技术领域", "select"),
        ListFilterSpec(
            "current",
            "当前版本",
            "select",
            choices=(("1", "是"), ("0", "否")),
        ),
    )

    def get_list_filter_specs(self):
        projects = SkillProject.objects.order_by("order", "code", "pk")
        domains = TechnicalDomain.objects.select_related("skill_project").order_by(
            "skill_project__order", "order", "code", "pk"
        )
        return (
            ListFilterSpec("project", "技能项目", "select", choices=[(item.pk, item) for item in projects]),
            ListFilterSpec("domain", "技术领域", "select", choices=[(item.pk, item) for item in domains]),
            self.list_filter_specs[2],
        )

    def get_base_queryset(self):
        return SkillTreeVersion.objects.select_related(
            "technical_domain",
            "technical_domain__skill_project",
            "based_on",
        )

    def apply_custom_filters(self, queryset):
        if project_id := self.request.GET.get("project"):
            queryset = queryset.filter(technical_domain__skill_project_id=project_id)
        if domain_id := self.request.GET.get("domain"):
            queryset = queryset.filter(technical_domain_id=domain_id)
        if current := self.request.GET.get("current"):
            queryset = queryset.filter(is_current=current == "1")
        return queryset


class SkillTreeVersionDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = SkillTreeVersion
    context_object_name = "tree"
    template_name = "standards/domain_tree.html"
    title = "{name}"
    permission_required = "standards.view_skilltreeversion"

    def get_queryset(self):
        return SkillTreeVersion.objects.select_related(
            "technical_domain",
            "technical_domain__skill_project",
            "based_on",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tree = self.object
        domain = skill_tree_structure(tree_version=tree, user=self.request.user)
        context.update(
            project=tree.skill_project,
            tree=tree,
            domain=domain,
            is_current_tree=tree.is_current,
            unmounted_skill_count=unmounted_primary_skills_for_tree(
                tree_version=tree,
                user=self.request.user,
            ).count(),
            can_attach_unmounted_skills=can_manage_domain(
                self.request.user,
                domain,
                permission="standards.add_skilltreenode",
            ),
            can_create_tree_version=can_manage_domain(
                self.request.user,
                domain,
                permission="standards.add_skilltreeversion",
            ),
            can_set_current=can_manage_domain(
                self.request.user,
                domain,
                permission="standards.change_skilltreeversion",
            ),
            version_context=True,
        )
        return context


class DomainSkillTreeMixin(TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "standards/domain_tree.html"
    title_icon = "icon-[tabler--hierarchy-3]"
    permission_required = "standards.view_skilltreeversion"

    def _set_tree_and_domain(self, *, tree):
        self.tree = tree
        self.project = tree.skill_project
        self.domain = tree.technical_domain

    def get_title(self):
        return f"{self.domain.name}技能树"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_attach = can_manage_domain(
            self.request.user,
            self.domain,
            permission="standards.add_skilltreenode",
        )
        context.update(
            project=self.project,
            tree=self.tree,
            domain=skill_tree_structure(tree_version=self.tree, user=self.request.user),
            is_current_tree=self.tree.is_current,
            unmounted_skill_count=unmounted_primary_skills_for_tree(
                tree_version=self.tree,
                user=self.request.user,
            ).count(),
            can_attach_unmounted_skills=can_attach,
            can_create_tree_version=can_manage_domain(
                self.request.user,
                self.domain,
                permission="standards.add_skilltreeversion",
            ),
            can_set_current=can_manage_domain(
                self.request.user,
                self.domain,
                permission="standards.change_skilltreeversion",
            ),
        )
        return context


class CurrentDomainSkillTreeView(DomainSkillTreeMixin):
    def dispatch(self, request, *args, **kwargs):
        project = get_object_or_404(SkillProject, pk=kwargs["project_pk"], is_active=True)
        domain = get_object_or_404(TechnicalDomain, pk=kwargs["domain_pk"], skill_project=project)
        tree = current_skill_tree_for(domain)
        if tree is not None:
            self._set_tree_and_domain(tree=tree)
        else:
            self.project = project
            self.domain = domain
            self.tree = None
        return super().dispatch(request, *args, **kwargs)

    def get_title(self):
        return f"{self.domain.name}当前技能树"

    def get_context_data(self, **kwargs):
        if self.tree is None:
            context = TemplateView.get_context_data(self, **kwargs)
            can_create_tree = can_manage_domain(
                self.request.user,
                self.domain,
                permission="standards.add_skilltreeversion",
            )
            context.update(
                project=self.project,
                domain=self.domain,
                current_tree_missing=True,
                can_create_tree_version=can_create_tree,
            )
            if can_create_tree:
                context["page_actions"] = [
                    {
                        "label": "新增技能树版本",
                        "href": reverse("standards:domain_tree_create", args=[self.project.pk, self.domain.pk]),
                        "icon": "icon-[tabler--plus]",
                        "variant_class": "btn-primary",
                        "size_class": "btn-sm",
                    }
                ]
            return context
        return super().get_context_data(**kwargs)


class SkillTreeVersionCreateView(StandardCreateMixin, TitleMixin, PermissionRequiredMixin, CreateView):
    model = SkillTreeVersion
    form_class = SkillTreeVersionForm
    title = "新增技能树版本"
    permission_required = "standards.add_skilltreeversion"
    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(SkillProject, pk=kwargs["project_pk"])
        self.domain = get_object_or_404(
            TechnicalDomain,
            pk=kwargs["domain_pk"],
            skill_project=self.project,
        )
        if not can_manage_domain(request.user, self.domain, permission=self.permission_required):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(technical_domain=self.domain, actor=self.request.user)
        return kwargs

    def get_success_url(self):
        return reverse("standards:tree_detail", args=[self.object.pk])


class SkillTreeVersionUpdateView(StandardCreateMixin, TitleMixin, PermissionRequiredMixin, UpdateView):
    model = SkillTreeVersion
    form_class = SkillTreeVersionForm
    title = "编辑技能树版本"
    permission_required = "standards.change_skilltreeversion"

    def get_queryset(self):
        return SkillTreeVersion.objects.select_related("technical_domain")

    def dispatch(self, request, *args, **kwargs):
        tree = self.get_object()
        if not can_manage_domain(request.user, tree.technical_domain, permission=self.permission_required):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(technical_domain=self.object.technical_domain, actor=self.request.user)
        return kwargs

    def get_success_url(self):
        return reverse("standards:tree_detail", args=[self.object.pk])


@require_POST
def skill_tree_set_current(request, tree_pk):
    tree = _tree_for_workbench(tree_pk)
    set_current_skill_tree_version(tree_version=tree, actor=request.user)
    messages.success(request, f"已将 {tree.technical_domain.name} / {tree.version} 设为当前技能树版本。")
    return redirect("standards:tree_detail", pk=tree.pk)


class SkillTreeNodeListView(
    FilterableListMixin,
    TitleMixin,
    PermissionRequiredMixin,
    SingleTableView,
):
    table_class = SkillTreeNodeTable
    template_name = "standards/tree_node_list.html"
    title_icon = "icon-[tabler--list-details]"
    permission_required = "standards.view_skilltreeversion"
    search_fields = ("skill__name", "skill__description", "skill__terms__term")
    search_requires_distinct = True
    list_filter_specs = (
        ListFilterSpec("q", "搜索", "search", placeholder="搜索技能名称、别名或描述"),
        ListFilterSpec("difficulty", "难度", "select", choices=tuple((value, value) for value in range(1, 6))),
        ListFilterSpec("core", "核心技能", "select", choices=(("1", "是"), ("0", "否"))),
        ListFilterSpec("assessable", "可考核", "select", choices=(("1", "是"), ("0", "否"))),
        ListFilterSpec("active", "启用状态", "select", choices=(("1", "启用"), ("0", "停用"))),
    )

    def dispatch(self, request, *args, **kwargs):
        if "tree_pk" in kwargs:
            self.tree = _tree_for_workbench(kwargs["tree_pk"])
            self.version_context = True
        else:
            project = get_object_or_404(SkillProject, pk=kwargs["project_pk"], is_active=True)
            domain = get_object_or_404(TechnicalDomain, pk=kwargs["domain_pk"], skill_project=project)
            self.tree = current_skill_tree_for(domain)
            if self.tree is None:
                return redirect("standards:current_domain_tree", project_pk=project.pk, domain_pk=domain.pk)
            self.version_context = False
        self.domain = self.tree.technical_domain
        self.project = self.tree.skill_project
        self.current_wsos = current_wsos_for(self.project)
        return super().dispatch(request, *args, **kwargs)

    def get_title(self):
        return f"{self.domain.name}技能列表"

    def get_list_filter_specs(self):
        specs = list(self.list_filter_specs)
        if self.current_wsos is not None:
            specs.append(
                ListFilterSpec(
                    "wsos",
                    "当前 WSOS 映射",
                    "select",
                    choices=(("mapped", "已映射"), ("unmapped", "未映射")),
                )
            )
        return specs

    def get_base_queryset(self):
        queryset = SkillTreeNode.objects.filter(tree_version=self.tree).select_related(
            "tree_version",
            "tree_version__technical_domain",
            "skill",
            "skill__primary_domain",
        )
        if self.current_wsos is not None:
            mapping = SkillWSOSMap.objects.filter(
                skill_id=OuterRef("skill_id"),
                wsos_section__wsos_version=self.current_wsos,
            )
            queryset = queryset.annotate(has_current_wsos_mapping=Exists(mapping))
        return queryset

    def apply_custom_filters(self, queryset):
        direct_filters = {
            "difficulty": "skill__difficulty",
            "core": "skill__is_core",
            "assessable": "skill__is_assessable",
            "active": "skill__is_active",
        }
        for parameter, lookup in direct_filters.items():
            if value := self.request.GET.get(parameter):
                queryset = queryset.filter(**{lookup: value if parameter == "difficulty" else value == "1"})
        if self.current_wsos is not None:
            if self.request.GET.get("wsos") == "mapped":
                queryset = queryset.filter(has_current_wsos_mapping=True)
            elif self.request.GET.get("wsos") == "unmapped":
                queryset = queryset.filter(has_current_wsos_mapping=False)
        return queryset

    def get_table_data(self):
        nodes = list(super().get_table_data())
        decorate_skill_tree_paths(tree_version=self.tree, nodes=nodes)
        for node in nodes:
            node.current_wsos_unavailable = self.current_wsos is None
            node.has_current_wsos_mapping = bool(getattr(node, "has_current_wsos_mapping", False))
            node.can_edit_skill = can_manage_skill(self.request.user, node.skill)
        return nodes

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            tree=self.tree,
            project=self.project,
            domain=self.domain,
            is_current_tree=self.tree.is_current,
            current_wsos=self.current_wsos,
            version_context=self.version_context,
            can_edit_version=can_manage_domain(
                self.request.user,
                self.domain,
                permission="standards.change_skilltreeversion",
            ),
        )
        return context


@require_GET
def skill_tree_search(request, tree_pk):
    if not request.user.has_perm("standards.view_skilltreeversion"):
        raise PermissionDenied
    tree = _tree_for_workbench(tree_pk)
    query = request.GET.get("q", "").strip()
    results = search_skill_tree_nodes(
        tree_version=tree,
        user=request.user,
        query=query,
    )
    return render(
        request,
        "standards/partials/skill_tree_search_results.html",
        {"tree": tree, "query": query, "results": results},
    )


def _tree_for_workbench(tree_pk):
    return get_object_or_404(
        SkillTreeVersion.objects.select_related("technical_domain", "technical_domain__skill_project"),
        pk=tree_pk,
    )


def _tree_node(tree, node_pk):
    return get_object_or_404(
        SkillTreeNode.objects.select_related(
            "skill",
            "skill__primary_domain",
            "tree_version",
            "tree_version__technical_domain",
            "parent",
            "parent__skill",
        ),
        pk=node_pk,
        tree_version=tree,
    )


def _tree_descendant_stats(tree, node):
    children_by_parent = {}
    for child_id, parent_id in SkillTreeNode.objects.filter(tree_version=tree).values_list("pk", "parent_id"):
        children_by_parent.setdefault(parent_id, []).append(child_id)
    direct_child_count = len(children_by_parent.get(node.pk, ()))
    count = 0
    stack = list(children_by_parent.get(node.pk, ()))
    while stack:
        current = stack.pop()
        count += 1
        stack.extend(children_by_parent.get(current, ()))
    return direct_child_count, count


def _render_tree_panel(request, tree, *, created_node_id=None, focused_node_id=None):
    response = render(
        request,
        "standards/partials/skill_tree_domain_panel.html",
        {
            "tree": tree,
            "domain": skill_tree_structure(tree_version=tree, user=request.user),
        },
    )
    events = {}
    if created_node_id is not None:
        events["skillTreeNodeCreated"] = {"nodeId": created_node_id}
    if focused_node_id is not None:
        events["skillTreeNodeFocused"] = {"nodeId": focused_node_id}
    if events:
        response.headers["HX-Trigger-After-Swap"] = json.dumps(events)
    return response


def skill_tree_panel(request, tree_pk):
    if not request.user.has_perm("standards.view_skilltreeversion"):
        raise PermissionDenied
    tree = _tree_for_workbench(tree_pk)
    return _render_tree_panel(request, tree)


def _root_placement(tree):
    return tree.technical_domain, None, None


def _child_placement(tree, parent_pk):
    parent = _tree_node(tree, parent_pk)
    return parent.technical_domain, parent, parent


def _sibling_placement(tree, node_pk):
    node = _tree_node(tree, node_pk)
    return node.technical_domain, node.parent, node


def _tree_editor_urls(*, tree, domain, kind, anchor):
    if kind == "root":
        return {
            "submit_url": reverse("standards:tree_quick_add_root", args=[tree.pk]),
            "candidates_url": reverse("standards:tree_candidates_root", args=[tree.pk]),
            "full_create_url": reverse("standards:tree_skill_create_root", args=[tree.pk]),
        }
    if kind == "child":
        return {
            "submit_url": reverse(
                "standards:tree_quick_add_child",
                args=[tree.pk, anchor.pk],
            ),
            "candidates_url": reverse(
                "standards:tree_candidates_child",
                args=[tree.pk, anchor.pk],
            ),
            "full_create_url": reverse("standards:tree_skill_create_child", args=[tree.pk, anchor.pk]),
        }
    return {
        "submit_url": reverse("standards:tree_quick_add_sibling", args=[tree.pk, anchor.pk]),
        "candidates_url": reverse("standards:tree_candidates_sibling", args=[tree.pk, anchor.pk]),
        "full_create_url": reverse("standards:tree_skill_create_sibling", args=[tree.pk, anchor.pk]),
    }


def _tree_candidates(*, tree, domain, query):
    candidates = find_skill_candidates(skill_project=tree.skill_project, query=query)
    candidate_ids = [candidate.pk for candidate in candidates]
    tree_nodes = list(
        SkillTreeNode.objects.filter(tree_version=tree)
        .select_related("skill")
        .order_by("order", "pk")
    ) if candidate_ids else []
    node_by_id = {node.pk: node for node in tree_nodes}
    existing_by_skill = {
        node.skill_id: node for node in tree_nodes if node.skill_id in candidate_ids
    }

    def path_for(node):
        parts = [node.skill.name]
        parent_id = node.parent_id
        while parent_id is not None:
            parent = node_by_id[parent_id]
            parts.append(parent.skill.name)
            parent_id = parent.parent_id
        return " / ".join(reversed(parts))

    for candidate in candidates:
        candidate.existing_tree_node = existing_by_skill.get(candidate.pk)
        candidate.existing_tree_path = (
            path_for(candidate.existing_tree_node) if candidate.existing_tree_node is not None else ""
        )
        candidate.domain_compatible = candidate.primary_domain_id == domain.pk or any(
            item.pk == domain.pk for item in candidate.related_domains.all()
        )
        candidate.can_attach_to_domain = (
            candidate.is_active
            and candidate.existing_tree_node is None
            and candidate.domain_compatible
        )
    return candidates


def _tree_inline_context(*, request, tree, domain, parent, kind, anchor, form, candidates=()):
    can_create_skill = can_manage_domain(request.user, domain, permission="standards.add_skill")
    return {
        "tree": tree,
        "domain": domain,
        "parent": parent,
        "inline_form": form,
        "candidates": candidates,
        "candidate_query": form.data.get("name", "") if form.is_bound else form.initial.get("name", ""),
        "has_high_similarity": any(
            candidate.candidate_high_similarity and not candidate.candidate_exact for candidate in candidates
        ),
        "can_create_skill": can_create_skill,
        **_tree_editor_urls(tree=tree, domain=domain, kind=kind, anchor=anchor),
    }


def _render_tree_inline_editor(*, request, tree, domain, parent, kind, anchor, form, candidates=()):
    return render(
        request,
        "standards/partials/skill_tree_inline_editor.html",
        _tree_inline_context(
            request=request,
            tree=tree,
            domain=domain,
            parent=parent,
            kind=kind,
            anchor=anchor,
            form=form,
            candidates=candidates,
        ),
    )


def _skill_tree_inline_editor(request, *, tree, domain, parent, kind, anchor):
    if not can_manage_domain(request.user, domain, permission="standards.add_skilltreenode"):
        raise PermissionDenied

    form = SkillTreeQuickAddForm(request.POST if request.method == "POST" else None)
    candidates = []
    if request.method == "POST" and form.is_valid():
        candidates = _tree_candidates(tree=tree, domain=domain, query=form.cleaned_data["name"])
        node = None
        try:
            if skill_id := form.cleaned_data.get("existing_skill_id"):
                skill = get_object_or_404(Skill, pk=skill_id, skill_project=tree.skill_project)
                node = attach_existing_skill_to_tree(
                    tree_version=tree,
                    parent=parent,
                    skill=skill,
                    actor=request.user,
                )
            else:
                exact = next((candidate for candidate in candidates if candidate.candidate_exact), None)
                high_similarity = [
                    candidate
                    for candidate in candidates
                    if candidate.candidate_high_similarity and not candidate.candidate_exact
                ]
                if exact is not None and exact.can_attach_to_domain:
                    node = attach_existing_skill_to_tree(
                        tree_version=tree,
                        parent=parent,
                        skill=exact,
                        actor=request.user,
                    )
                elif exact is None and not high_similarity:
                    if not can_manage_domain(request.user, domain, permission="standards.add_skill"):
                        form.add_error(
                            "name",
                            "你可以将已有技能挂入此位置，但没有创建新技能的权限。",
                        )
                    else:
                        node = create_skill_in_tree(
                            tree_version=tree,
                            parent=parent,
                            name=form.cleaned_data["name"],
                            actor=request.user,
                        )
                # 精确候选已在树中、不可挂载，或存在高度相似候选时保留编辑器供用户选择。
                if node is None:
                    return _render_tree_inline_editor(
                        request=request,
                        tree=tree,
                        domain=domain,
                        parent=parent,
                        kind=kind,
                        anchor=anchor,
                        form=form,
                        candidates=candidates,
                    )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            if node is not None:
                response = _render_tree_panel(request, tree, created_node_id=node.pk)
                response.headers["HX-Retarget"] = "#skill-tree-panel"
                response.headers["HX-Reswap"] = "outerHTML"
                return response
    if request.method == "POST" and form.data.get("name") and not candidates:
        candidates = _tree_candidates(tree=tree, domain=domain, query=form.data["name"])
    return _render_tree_inline_editor(
        request=request,
        tree=tree,
        domain=domain,
        parent=parent,
        kind=kind,
        anchor=anchor,
        form=form,
        candidates=candidates,
    )


@require_http_methods(["GET", "POST"])
def skill_tree_quick_add(request, tree_pk, parent_pk=None):
    tree = _tree_for_workbench(tree_pk)
    if parent_pk is None:
        domain, parent, anchor = _root_placement(tree)
        kind = "root"
    else:
        domain, parent, anchor = _child_placement(tree, parent_pk)
        kind = "child"
    return _skill_tree_inline_editor(
        request,
        tree=tree,
        domain=domain,
        parent=parent,
        kind=kind,
        anchor=anchor,
    )


@require_http_methods(["GET", "POST"])
def skill_tree_quick_add_sibling(request, tree_pk, node_pk):
    tree = _tree_for_workbench(tree_pk)
    domain, parent, anchor = _sibling_placement(tree, node_pk)
    return _skill_tree_inline_editor(
        request,
        tree=tree,
        domain=domain,
        parent=parent,
        kind="sibling",
        anchor=anchor,
    )


def _skill_tree_candidate_fragment(request, *, tree, domain, parent, kind, anchor):
    if not can_manage_domain(request.user, domain, permission="standards.add_skilltreenode"):
        raise PermissionDenied
    query = request.GET.get("name", "")
    form = SkillTreeQuickAddForm(initial={"name": query})
    candidates = _tree_candidates(tree=tree, domain=domain, query=query)
    return render(
        request,
        "standards/partials/skill_tree_candidates.html",
        _tree_inline_context(
            request=request,
            tree=tree,
            domain=domain,
            parent=parent,
            kind=kind,
            anchor=anchor,
            form=form,
            candidates=candidates,
        ),
    )


@require_GET
def skill_tree_candidates(request, tree_pk, parent_pk=None):
    tree = _tree_for_workbench(tree_pk)
    if parent_pk is None:
        domain, parent, anchor = _root_placement(tree)
        kind = "root"
    else:
        domain, parent, anchor = _child_placement(tree, parent_pk)
        kind = "child"
    return _skill_tree_candidate_fragment(
        request,
        tree=tree,
        domain=domain,
        parent=parent,
        kind=kind,
        anchor=anchor,
    )


@require_GET
def skill_tree_candidates_sibling(request, tree_pk, node_pk):
    tree = _tree_for_workbench(tree_pk)
    domain, parent, anchor = _sibling_placement(tree, node_pk)
    return _skill_tree_candidate_fragment(
        request,
        tree=tree,
        domain=domain,
        parent=parent,
        kind="sibling",
        anchor=anchor,
    )


def _tree_skill_form(*, request, tree, domain, instance=None):
    data = None
    if request.method == "POST":
        data = request.POST.copy()
        data["skill_project"] = tree.skill_project_id if instance is None else instance.skill_project_id
        if instance is None:
            data["primary_domain"] = domain.pk
    initial = None
    if instance is None:
        initial = {
            "skill_project": tree.skill_project,
            "primary_domain": domain,
            "name": request.GET.get("name", "").strip(),
        }
    form = SkillForm(data=data, initial=initial, instance=instance, user=request.user)
    form.fields["skill_project"].widget = forms.HiddenInput()
    if instance is None:
        form.fields["primary_domain"].widget = forms.HiddenInput()
    else:
        for attribute in ("hx-get", "hx-target", "hx-trigger", "hx-include"):
            form.fields["name"].widget.attrs.pop(attribute, None)
    return form


def _tree_skill_candidates(*, request, tree, form, exclude_skill=None):
    query = form.data.get("name", "") if form.is_bound else form.initial.get("name", "")
    if not query or exclude_skill is not None:
        return query, []
    candidates = _decorate_candidate_permissions(
        request.user,
        find_skill_candidates(
            skill_project=tree.skill_project,
            query=query,
            exclude_skill=exclude_skill,
        ),
    )
    return query, candidates


def _render_tree_skill_dialog(*, request, tree, domain, parent, node, form, action_url, candidates=()):
    candidate_query = form.data.get("name", "") if form.is_bound else form.initial.get("name", "")
    return render(
        request,
        "standards/partials/skill_tree_skill_form_dialog.html",
        {
            "tree": tree,
            "domain": domain,
            "parent": parent,
            "node": node,
            "skill_form": form,
            "form_action": action_url,
            "is_edit": node is not None,
            "candidates": candidates,
            "candidate_query": candidate_query,
            "has_high_similarity": any(
                candidate.candidate_high_similarity and not candidate.candidate_exact for candidate in candidates
            ),
        },
    )


def _skill_tree_detailed_create(request, *, tree, domain, parent, action_url):
    if not can_manage_domain(request.user, domain, permission="standards.add_skill"):
        raise PermissionDenied
    if not can_manage_domain(request.user, domain, permission="standards.add_skilltreenode"):
        raise PermissionDenied

    form = _tree_skill_form(request=request, tree=tree, domain=domain)
    is_valid = request.method == "POST" and form.is_valid()
    _, candidates = _tree_skill_candidates(request=request, tree=tree, form=form)
    high_similarity = [
        candidate for candidate in candidates if candidate.candidate_high_similarity and not candidate.candidate_exact
    ]
    if is_valid and high_similarity and not form.cleaned_data.get("confirm_distinct"):
        form.add_error("confirm_distinct", "请先确认候选技能与当前技能并非同一技能。")
    if is_valid and high_similarity and not form.cleaned_data.get("description", "").strip():
        form.add_error("description", "存在高相似候选时，请填写描述说明技能边界。")

    if is_valid and not form.errors:
        skill = form.save(commit=False)
        try:
            node = create_detailed_skill_in_tree(
                tree_version=tree,
                parent=parent,
                skill=skill,
                aliases=form._split_text(form.cleaned_data.get("aliases_text")),
                related_domains=form.cleaned_data.get("related_domains", ()),
                actor=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            response = _render_tree_panel(request, tree, created_node_id=node.pk)
            response.headers["HX-Retarget"] = "#skill-tree-panel"
            response.headers["HX-Reswap"] = "outerHTML"
            return response

    return _render_tree_skill_dialog(
        request=request,
        tree=tree,
        domain=domain,
        parent=parent,
        node=None,
        form=form,
        action_url=action_url,
        candidates=candidates,
    )


@require_http_methods(["GET", "POST"])
def skill_tree_detailed_create_root(request, tree_pk):
    tree = _tree_for_workbench(tree_pk)
    domain, parent, _ = _root_placement(tree)
    action_url = reverse("standards:tree_skill_create_root", args=[tree.pk])
    return _skill_tree_detailed_create(
        request,
        tree=tree,
        domain=domain,
        parent=parent,
        action_url=action_url,
    )


@require_http_methods(["GET", "POST"])
def skill_tree_detailed_create_child(request, tree_pk, parent_pk):
    tree = _tree_for_workbench(tree_pk)
    domain, parent, _ = _child_placement(tree, parent_pk)
    action_url = reverse("standards:tree_skill_create_child", args=[tree.pk, parent.pk])
    return _skill_tree_detailed_create(
        request,
        tree=tree,
        domain=domain,
        parent=parent,
        action_url=action_url,
    )


@require_http_methods(["GET", "POST"])
def skill_tree_detailed_create_sibling(request, tree_pk, node_pk):
    tree = _tree_for_workbench(tree_pk)
    domain, parent, anchor = _sibling_placement(tree, node_pk)
    action_url = reverse("standards:tree_skill_create_sibling", args=[tree.pk, anchor.pk])
    return _skill_tree_detailed_create(
        request,
        tree=tree,
        domain=domain,
        parent=parent,
        action_url=action_url,
    )


@require_http_methods(["GET", "POST"])
def skill_tree_skill_edit(request, tree_pk, node_pk):
    tree = _tree_for_workbench(tree_pk)
    node = _tree_node(tree, node_pk)
    if not request.user.has_perm("standards.change_skill"):
        raise PermissionDenied
    if not can_manage_skill(request.user, node.skill):
        raise Http404

    form = _tree_skill_form(
        request=request,
        tree=tree,
        domain=node.technical_domain,
        instance=node.skill,
    )
    if request.method == "POST" and form.is_valid():
        skill = form.save(commit=False)
        try:
            save_skill(
                skill=skill,
                aliases=form._split_text(form.cleaned_data.get("aliases_text")),
                related_domains=form.cleaned_data.get("related_domains", ()),
                preserve_old_name=form.cleaned_data.get("preserve_old_name", False),
                old_name=form.old_name,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            response = _render_tree_panel(request, tree, focused_node_id=node.pk)
            response.headers["HX-Retarget"] = "#skill-tree-panel"
            response.headers["HX-Reswap"] = "outerHTML"
            return response

    return _render_tree_skill_dialog(
        request=request,
        tree=tree,
        domain=node.technical_domain,
        parent=node.parent,
        node=node,
        form=form,
        action_url=reverse("standards:tree_node_skill_edit", args=[tree.pk, node.pk]),
    )


def skill_tree_move(request, tree_pk, node_pk):
    tree = _tree_for_workbench(tree_pk)
    node = _tree_node(tree, node_pk)
    if not can_manage_domain(request.user, node.technical_domain, permission="standards.change_skilltreenode"):
        raise PermissionDenied
    form_data = request.POST if request.method == "POST" else request.GET if request.GET else None
    form = SkillTreeMoveForm(
        form_data,
        tree_version=tree,
        node=node,
    )
    if request.method == "POST" and form.is_valid():
        parent_id = form.cleaned_data.get("new_parent")
        new_parent = _tree_node(tree, int(parent_id)) if parent_id else None
        try:
            move_skill_tree_node(
                node=node,
                new_parent=new_parent,
                actor=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            response = _render_tree_panel(request, tree, focused_node_id=node.pk)
            response.headers["HX-Retarget"] = "#skill-tree-panel"
            response.headers["HX-Reswap"] = "outerHTML"
            return response
    return render(
        request,
        "standards/partials/skill_tree_move_dialog.html",
        {"tree": tree, "node": node, "move_form": form},
    )


@require_POST
def skill_tree_reorder(request, tree_pk, node_pk):
    tree = _tree_for_workbench(tree_pk)
    node = _tree_node(tree, node_pk)
    try:
        reorder_skill_tree_node(
            node=node,
            direction=request.POST.get("direction", ""),
            actor=request.user,
        )
    except ValidationError as exc:
        return HttpResponseBadRequest(exc.message)
    return _render_tree_panel(request, tree)


def skill_tree_remove(request, tree_pk, node_pk):
    tree = _tree_for_workbench(tree_pk)
    node = _tree_node(tree, node_pk)
    if not can_manage_domain(request.user, node.technical_domain, permission="standards.delete_skilltreenode"):
        raise PermissionDenied
    direct_child_count, descendant_count = _tree_descendant_stats(tree, node)
    form_data = request.POST.copy() if request.method == "POST" else None
    if descendant_count == 0 and form_data is not None:
        form_data["mode"] = "promote_children"
    form = SkillTreeRemoveForm(form_data, initial={"mode": "promote_children"})
    if descendant_count:
        form.fields["mode"].choices = (
            (
                "promote_children",
                f"仅移除当前技能，并将 {direct_child_count} 个直接子技能提升一级（推荐）",
            ),
            ("subtree", f"移除整个分支，共 {descendant_count + 1} 个树位置"),
        )
    if request.method == "POST" and form.is_valid():
        try:
            remove_skill_tree_node(
                node=node,
                mode=form.cleaned_data["mode"],
                actor=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            response = _render_tree_panel(request, tree)
            response.headers["HX-Retarget"] = "#skill-tree-panel"
            response.headers["HX-Reswap"] = "outerHTML"
            return response
    return render(
        request,
        "standards/partials/skill_tree_remove_dialog.html",
        {
            "tree": tree,
            "node": node,
            "remove_form": form,
            "direct_child_count": direct_child_count,
            "descendant_count": descendant_count,
            "subtree_count": descendant_count + 1,
        },
    )


@require_GET
def skill_tree_unmounted_skills(request, tree_pk):
    tree = _tree_for_workbench(tree_pk)
    domain = tree.technical_domain
    if not request.user.has_perm("standards.view_skilltreeversion"):
        raise PermissionDenied
    return render(
        request,
        "standards/partials/skill_tree_unmounted_skills_dialog.html",
        {
            "tree": tree,
            "domain": domain,
            "skills": unmounted_primary_skills_for_tree(
                tree_version=tree,
                user=request.user,
            ),
            "can_attach_unmounted_skills": can_manage_domain(
                request.user,
                domain,
                permission="standards.add_skilltreenode",
            ),
        },
    )


@require_http_methods(["GET", "POST"])
def skill_tree_attach_existing(request, tree_pk, skill_pk):
    tree = _tree_for_workbench(tree_pk)
    domain = tree.technical_domain
    skill = get_object_or_404(
        unmounted_primary_skills_for_tree(
            tree_version=tree,
            user=request.user,
        ),
        pk=skill_pk,
    )
    if not can_manage_domain(request.user, domain, permission="standards.add_skilltreenode"):
        raise PermissionDenied
    form = SkillTreeAttachExistingForm(
        request.POST if request.method == "POST" else None,
        tree_version=tree,
    )
    if request.method == "POST" and form.is_valid():
        try:
            node = attach_existing_skill_to_tree(
                tree_version=tree,
                parent=form.cleaned_data["new_parent"],
                skill=skill,
                actor=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            response = _render_tree_panel(request, tree, created_node_id=node.pk)
            response.headers["HX-Retarget"] = "#skill-tree-panel"
            response.headers["HX-Reswap"] = "outerHTML"
            return response
    return render(
        request,
        "standards/partials/skill_tree_attach_existing_dialog.html",
        {"tree": tree, "domain": domain, "skill": skill, "attach_form": form},
    )


class WSOSVersionListView(StandardListMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = WSOSVersion
    table_class = WSOSVersionTable
    title = "WSOS"
    permission_required = "standards.view_wsosversion"
    create_url_name = "standards:wsos_create"
    create_label = "新增 WSOS 版本"


class WSOSVersionDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = WSOSVersion
    context_object_name = "wsos"
    template_name = "standards/wsos_detail.html"
    title = "{name}"
    permission_required = "standards.view_wsosversion"

    def get_queryset(self):
        return WSOSVersion.objects.select_related("skill_project")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = self.object.sections.annotate(
            mapped_skill_count=Count("skill_mappings", distinct=True)
        ).prefetch_related("skill_mappings__skill")
        context.update(
            sections=sections,
            weight_total=sections.aggregate(total=Sum("weight"))["total"] or 0,
            mapping_domains=TechnicalDomain.objects.filter(skill_project=self.object.skill_project).order_by(
                "order", "code", "pk"
            ),
        )
        return context


class WSOSVersionCreateView(StandardCreateMixin, TitleMixin, PermissionRequiredMixin, CreateView):
    model = WSOSVersion
    form_class = WSOSVersionForm
    title = "新增 WSOS 版本"
    permission_required = "standards.add_wsosversion"
    success_url_name = "standards:wsos_detail"


class WSOSVersionUpdateView(WSOSVersionCreateView, UpdateView):
    title = "编辑 WSOS 版本"
    permission_required = "standards.change_wsosversion"


class WSOSSectionCreateView(StandardCreateMixin, TitleMixin, PermissionRequiredMixin, CreateView):
    model = WSOSSection
    form_class = WSOSSectionForm
    title = "新增 WSOS 章节"
    permission_required = "standards.add_wsossection"

    def dispatch(self, request, *args, **kwargs):
        self.wsos = get_object_or_404(WSOSVersion, pk=kwargs["wsos_pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.wsos_version = self.wsos
        return super().form_valid(form)

    def get_success_url(self):
        return f"{reverse('standards:wsos_detail', args=[self.wsos.pk])}#section-{self.object.pk}"


class WSOSSectionUpdateView(StandardCreateMixin, TitleMixin, PermissionRequiredMixin, UpdateView):
    model = WSOSSection
    form_class = WSOSSectionForm
    title = "编辑 WSOS 章节"
    permission_required = "standards.change_wsossection"

    def get_queryset(self):
        return WSOSSection.objects.select_related("wsos_version")

    def get_success_url(self):
        return f"{reverse('standards:wsos_detail', args=[self.object.wsos_version_id])}#section-{self.object.pk}"


@require_http_methods(["GET", "POST"])
def wsos_section_delete(request, section_pk):
    section = get_object_or_404(WSOSSection.objects.select_related("wsos_version"), pk=section_pk)
    if not request.user.has_perm("standards.delete_wsossection"):
        raise PermissionDenied
    if request.method == "POST":
        try:
            wsos_pk = section.wsos_version_id
            delete_wsos_section(section=section, actor=request.user)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, "WSOS 章节已删除。")
        return redirect("standards:wsos_detail", pk=wsos_pk)
    return render(
        request,
        "standards/confirm_delete.html",
        {
            "object": section,
            "title": "删除 WSOS 章节",
            "message": "删除前必须先解除该章节的全部技能映射。",
            "cancel_url": reverse("standards:wsos_detail", args=[section.wsos_version_id]),
        },
    )


@require_GET
def wsos_section_skill_candidates(request, section_pk):
    if not (
        request.user.has_perm("standards.view_skillwsosmap")
        or request.user.has_perm("standards.add_skillwsosmap")
    ):
        raise PermissionDenied
    section = get_object_or_404(WSOSSection.objects.select_related("wsos_version"), pk=section_pk)
    domain = None
    if domain_id := request.GET.get("domain"):
        domain = get_object_or_404(
            TechnicalDomain,
            pk=domain_id,
            skill_project=section.wsos_version.skill_project,
        )
    query = request.GET.get("q", "").strip()
    return render(
        request,
        "standards/partials/wsos_skill_candidates.html",
        {
            "section": section,
            "query": query,
            "selected_domain": domain,
            "candidates": wsos_skill_candidates(section=section, query=query, domain=domain),
        },
    )


@require_http_methods(["GET", "POST"])
def wsos_section_map_skill(request, section_pk, skill_pk):
    section = get_object_or_404(WSOSSection.objects.select_related("wsos_version"), pk=section_pk)
    skill = get_object_or_404(
        Skill.objects.filter(skill_project=section.wsos_version.skill_project, is_active=True),
        pk=skill_pk,
    )
    if not request.user.has_perm("standards.add_skillwsosmap"):
        raise PermissionDenied
    existing = SkillWSOSMap.objects.filter(skill=skill, wsos_section=section).first()
    if existing is not None:
        messages.info(request, "该技能已关联当前 WSOS 章节，原说明未被修改。")
        return redirect(f"{reverse('standards:wsos_detail', args=[section.wsos_version_id])}#section-{section.pk}")
    form = SkillWSOSMapNoteForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        mapping, _ = map_skill_to_wsos_section(
            skill=skill,
            section=section,
            actor=request.user,
            note=form.cleaned_data.get("note", ""),
        )
        messages.success(request, f"已关联技能“{mapping.skill.name}”。")
        return redirect(f"{reverse('standards:wsos_detail', args=[section.wsos_version_id])}#section-{section.pk}")
    return render(
        request,
        "standards/partials/wsos_mapping_form.html",
        {"section": section, "skill": skill, "mapping_form": form},
    )


@require_http_methods(["GET", "POST"])
def wsos_mapping_note_edit(request, mapping_pk):
    mapping = get_object_or_404(
        SkillWSOSMap.objects.select_related("skill", "wsos_section", "wsos_section__wsos_version"),
        pk=mapping_pk,
    )
    if not request.user.has_perm("standards.change_skillwsosmap"):
        raise PermissionDenied
    form = SkillWSOSMapNoteForm(request.POST if request.method == "POST" else None, instance=mapping)
    if request.method == "POST" and form.is_valid():
        update_skill_wsos_map_note(
            mapping=mapping,
            note=form.cleaned_data.get("note", ""),
            actor=request.user,
        )
        messages.success(request, "映射说明已更新。")
        return redirect(
            f"{reverse('standards:wsos_detail', args=[mapping.wsos_section.wsos_version_id])}"
            f"#section-{mapping.wsos_section_id}"
        )
    return render(
        request,
        "standards/partials/wsos_mapping_form.html",
        {"section": mapping.wsos_section, "skill": mapping.skill, "mapping": mapping, "mapping_form": form},
    )


@require_http_methods(["GET", "POST"])
def wsos_mapping_delete(request, mapping_pk):
    mapping = get_object_or_404(
        SkillWSOSMap.objects.select_related("skill", "wsos_section", "wsos_section__wsos_version"),
        pk=mapping_pk,
    )
    if not request.user.has_perm("standards.delete_skillwsosmap"):
        raise PermissionDenied
    if request.method == "POST":
        wsos_pk = mapping.wsos_section.wsos_version_id
        section_pk = mapping.wsos_section_id
        skill_name = mapping.skill.name
        unmap_skill_from_wsos_section(mapping=mapping, actor=request.user)
        messages.success(request, f"已解除技能“{skill_name}”的映射。")
        return redirect(f"{reverse('standards:wsos_detail', args=[wsos_pk])}#section-{section_pk}")
    return render(
        request,
        "standards/confirm_delete.html",
        {
            "object": mapping,
            "title": "解除技能映射",
            "message": "只会删除当前 Skill 与 WSOS 章节之间的这一条映射。",
            "cancel_url": f"{reverse('standards:wsos_detail', args=[mapping.wsos_section.wsos_version_id])}"
            f"#section-{mapping.wsos_section_id}",
        },
    )
