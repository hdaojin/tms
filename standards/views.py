import json
from urllib.parse import urlencode

from django import forms
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import BooleanField, Case, Count, Exists, OuterRef, Q, Value, When
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .forms import (
    SkillForm,
    SkillProjectForm,
    SkillTreeMoveForm,
    SkillTreeQuickAddForm,
    SkillTreeRemoveForm,
    SkillTreeVersionForm,
    TechnicalDomainForm,
    WSOSVersionForm,
)
from .models import Skill, SkillProject, SkillTreeNode, SkillTreeVersion, TechnicalDomain, WSOSVersion
from .selectors import (
    can_manage_domain,
    can_manage_skill,
    is_project_admin,
    manageable_domains_for,
    manageable_skills_for,
    skill_assessment_history,
    skill_assessment_performance,
    skill_tree_structure,
    skill_training_investment,
    visible_skills_for,
)
from .services import (
    add_skill_alias,
    attach_existing_skill_to_tree,
    create_skill_in_tree,
    find_skill_candidates,
    move_skill_tree_node,
    remove_skill_tree_node,
    reorder_skill_tree_node,
    save_skill,
)
from .tables import (
    SkillProjectTable,
    SkillTable,
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
            "standards:domain_detail",
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


class SkillCatalogEntryView(TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "standards/skill_catalog_project_select.html"
    title = "选择技能项目"
    title_icon = "icon-[tabler--target]"
    permission_required = "standards.view_skill"

    def get(self, request, *args, **kwargs):
        projects = SkillProject.objects.filter(is_active=True)
        project = projects.filter(is_default=True).first()
        if project is None and projects.count() == 1:
            project = projects.first()
        if project is not None:
            return redirect("standards:skill_list", project_pk=project.pk)
        if not projects.exists():
            raise Http404
        self.projects = projects
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["projects"] = self.projects
        return context


class SkillCatalogView(TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "standards/skill_catalog.html"
    title_icon = "icon-[tabler--target]"
    permission_required = "standards.view_skill"

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(SkillProject, pk=kwargs["project_pk"], is_active=True)
        return super().dispatch(request, *args, **kwargs)

    def get_title(self):
        return f"{self.project.name}技能目录"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visible_skills = visible_skills_for(self.request.user).filter(
            skill_project=self.project,
            is_active=True,
        )
        domains = TechnicalDomain.objects.filter(skill_project=self.project).select_related("skill_project")
        if self.request.user.has_perm("standards.change_technicaldomain"):
            manageable_inactive = manageable_domains_for(self.request.user, self.project).filter(is_active=False)
            domains = domains.filter(Q(is_active=True) | Q(pk__in=manageable_inactive))
        else:
            domains = domains.filter(is_active=True)
        domains = domains.annotate(
            visible_primary_skill_count=Count(
                "primary_skills",
                filter=Q(primary_skills__in=visible_skills),
                distinct=True,
            ),
            visible_related_skill_count=Count(
                "related_skills",
                filter=Q(related_skills__in=visible_skills),
                distinct=True,
            ),
        )
        for domain in domains:
            domain.can_edit_domain = can_manage_domain(self.request.user, domain)
        context["project"] = self.project
        context["domains"] = domains
        context["can_view_domain_management"] = self.request.user.has_perm("standards.view_technicaldomain")
        if self.request.user.has_perm("standards.add_technicaldomain"):
            context["page_actions"] = [
                {
                    "label": "新增技术领域",
                    "href": reverse("standards:domain_create", kwargs={"project_pk": self.project.pk}),
                    "icon": "icon-[tabler--plus]",
                    "variant_class": "btn-primary",
                    "size_class": "btn-sm",
                }
            ]
        return context


class TechnicalDomainDetailView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = Skill
    table_class = SkillTable
    template_name = "standards/domain_detail.html"
    title_icon = "icon-[tabler--target]"
    permission_required = "standards.view_skill"
    paginate_by = 25

    filter_names = ("q", "active", "core", "assessable", "related")

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(SkillProject, pk=kwargs["project_pk"], is_active=True)
        self.domain = get_object_or_404(
            TechnicalDomain.objects.select_related("skill_project").prefetch_related("memberships__user"),
            pk=kwargs["domain_pk"],
            skill_project=self.project,
        )
        if not self.domain.is_active and not can_manage_domain(request.user, self.domain):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_title(self):
        return f"{self.domain.name}技术领域"

    def get_filter_value(self, name):
        if name == "active" and name not in self.request.GET:
            return "1"
        return (self.request.GET.get(name, "") or "").strip()

    def get_queryset(self):
        queryset = (
            visible_skills_for(self.request.user)
            .filter(skill_project=self.project)
            .select_related("skill_project", "primary_domain")
            .prefetch_related("related_domains", "terms")
        )
        if self.get_filter_value("related") == "1":
            queryset = queryset.filter(Q(primary_domain=self.domain) | Q(related_domains=self.domain))
        else:
            queryset = queryset.filter(primary_domain=self.domain)
        if is_project_admin(self.request.user):
            queryset = queryset.annotate(can_edit_skill=Value(True, output_field=BooleanField()))
        else:
            queryset = queryset.annotate(
                can_edit_skill=Exists(
                    TechnicalDomain.objects.filter(
                        pk=OuterRef("primary_domain_id"),
                        memberships__user=self.request.user,
                    )
                )
            )
        if active := self.get_filter_value("active"):
            queryset = queryset.filter(is_active=active == "1")
        if core := self.get_filter_value("core"):
            queryset = queryset.filter(is_core=core == "1")
        if assessable := self.get_filter_value("assessable"):
            queryset = queryset.filter(is_assessable=assessable == "1")
        if query := self.get_filter_value("q"):
            condition = Q(name__icontains=query) | Q(description__icontains=query) | Q(terms__term__icontains=query)
            queryset = queryset.filter(condition)
        queryset = queryset.annotate(
            is_related_match=Case(
                When(primary_domain=self.domain, then=Value(False)),
                default=Value(True),
                output_field=BooleanField(),
            )
        ).distinct()
        highlight = self.request.GET.get("highlight") or getattr(self, "highlight_skill_id", None)
        if highlight:
            for skill in queryset:
                skill.is_highlighted = str(skill.pk) == str(highlight)
            return queryset
        return queryset

    def get_form(self, data=None):
        if data is not None:
            data = data.copy()
            data["skill_project"] = self.project.pk
            data["primary_domain"] = self.domain.pk
        form = SkillForm(
            data=data,
            initial={"skill_project": self.project, "primary_domain": self.domain},
            user=self.request.user,
        )
        form.fields["skill_project"].widget = forms.HiddenInput()
        form.fields["primary_domain"].widget = forms.HiddenInput()
        return form

    def get_table_kwargs(self):
        kwargs = super().get_table_kwargs()
        if self.get_filter_value("related") != "1":
            kwargs["exclude"] = ("relationship",)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project
        context["domain"] = self.domain
        context["can_view_domain_management"] = self.request.user.has_perm("standards.view_technicaldomain")
        context["can_edit_domain"] = can_manage_domain(self.request.user, self.domain)
        context["can_add_skill"] = can_manage_domain(
            self.request.user,
            self.domain,
            permission="standards.add_skill",
        )
        context["focus_create"] = self.request.GET.get("focus") == "create"
        if context["can_add_skill"]:
            create_query = self.request.GET.copy()
            create_query["focus"] = "create"
            context["page_actions"] = [
                {
                    "label": "新增技能",
                    "href": f"{reverse('standards:domain_detail', kwargs={'project_pk': self.project.pk, 'domain_pk': self.domain.pk})}?{create_query.urlencode()}",
                    "icon": "icon-[tabler--plus]",
                    "variant_class": "btn-primary",
                    "size_class": "btn-sm",
                    "extra_class": "js-skill-drawer-open",
                }
            ]
        context["skill_form"] = kwargs.get("skill_form") or self.get_form()
        context["filter_values"] = {name: self.get_filter_value(name) for name in self.filter_names}
        context["candidate_url"] = reverse("standards:skill_candidates")
        context["domain_fields_url"] = reverse("standards:skill_domain_fields")
        return context

    def _highlight_page_if_requested(self):
        highlight = self.request.GET.get("highlight")
        if not highlight:
            return
        ids = list(self.object_list.values_list("pk", flat=True))
        try:
            position = ids.index(int(highlight))
        except (ValueError, TypeError):
            return
        expected_page = position // self.paginate_by + 1
        if self.request.GET.get("page") != str(expected_page):
            query = self.request.GET.copy()
            query["page"] = expected_page
            self.request.GET = query

    def _created_skill_url(self, skill, filtered_ids):
        params = {name: self.get_filter_value(name) for name in self.filter_names}
        if skill.pk not in filtered_ids:
            params = {}
        params["highlight"] = skill.pk
        path = reverse(
            "standards:domain_detail",
            kwargs={"project_pk": self.project.pk, "domain_pk": self.domain.pk},
        )
        return f"{path}?{urlencode({key: value for key, value in params.items() if value})}"

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        self._highlight_page_if_requested()
        context = self.get_context_data()
        if request.htmx:
            return render(request, "standards/partials/skill_results.html", context)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("standards.add_skill"):
            raise PermissionDenied
        form = self.get_form(data=request.POST)
        candidates = []
        if form.is_valid():
            candidates = _decorate_candidate_permissions(
                request.user,
                find_skill_candidates(
                    skill_project=form.cleaned_data["skill_project"],
                    query=form.cleaned_data["name"],
                ),
            )
            high_similarity = [candidate for candidate in candidates if candidate.candidate_high_similarity]
            if high_similarity and not form.cleaned_data.get("confirm_distinct"):
                form.add_error("confirm_distinct", "请先确认候选技能与当前技能并非同一技能。")
            if high_similarity and not form.cleaned_data.get("description", "").strip():
                form.add_error("description", "存在高相似候选时，请填写描述说明技能边界。")
        if form.is_valid():
            skill = form.save(commit=False)
            try:
                save_skill(
                    skill=skill,
                    aliases=form._split_text(form.cleaned_data.get("aliases_text")),
                    related_domains=form.cleaned_data.get("related_domains", ()),
                )
            except ValidationError as exc:
                form.add_error(None, exc.message)
            else:
                self.highlight_skill_id = skill.pk
                self.object_list = self.get_queryset()
                filtered_ids = list(self.object_list.values_list("pk", flat=True))
                try:
                    current_page = int(request.GET.get("page", "1") or 1)
                except ValueError:
                    current_page = 1
                target_page = filtered_ids.index(skill.pk) // self.paginate_by + 1 if skill.pk in filtered_ids else None
                context = self.get_context_data(skill_form=self.get_form())
                context["create_success"] = f"已新增技能「{skill.name}」。"
                if target_page != current_page:
                    context["created_catalog_url"] = self._created_skill_url(skill, filtered_ids)
                    context["created_hidden_by_filters"] = target_page is None
                response = render(request, "standards/partials/skill_create_response.html", context)
                response.headers["HX-Trigger-After-Swap"] = json.dumps({"skillCreated": {"skillId": skill.pk}})
                return response

        self.object_list = self.get_queryset()
        context = self.get_context_data(skill_form=form)
        context["candidates"] = candidates
        context["candidate_query"] = form.data.get("name", "")
        context["has_high_similarity"] = any(
            candidate.candidate_high_similarity and not candidate.candidate_exact for candidate in candidates
        )
        return render(request, "standards/partials/skill_form_panel.html", context)


def skill_form_reset(request, project_pk, domain_pk):
    if not request.user.has_perm("standards.add_skill"):
        raise PermissionDenied
    project = get_object_or_404(SkillProject, pk=project_pk, is_active=True)
    domain = get_object_or_404(TechnicalDomain, pk=domain_pk, skill_project=project, is_active=True)
    if not can_manage_domain(request.user, domain, permission="standards.add_skill"):
        raise Http404
    form = SkillForm(
        user=request.user,
        initial={"skill_project": project, "primary_domain": domain},
    )
    form.fields["skill_project"].widget = forms.HiddenInput()
    form.fields["primary_domain"].widget = forms.HiddenInput()
    return render(
        request,
        "standards/partials/skill_form_panel.html",
        {"skill_form": form, "project": project, "domain": domain},
    )


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


class SkillTreeVersionListView(StandardListMixin, TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = SkillTreeVersion
    table_class = SkillTreeVersionTable
    title = "技能树"
    permission_required = "standards.view_skilltreeversion"
    create_url_name = "standards:tree_create"
    create_label = "新增技能树版本"


class SkillTreeVersionDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = SkillTreeVersion
    context_object_name = "tree"
    template_name = "standards/tree_detail.html"
    title = "{name}"
    permission_required = "standards.view_skilltreeversion"

    def get_queryset(self):
        return SkillTreeVersion.objects.select_related("skill_project")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tree_domains"] = skill_tree_structure(tree_version=self.object, user=self.request.user)
        context["quick_add_form"] = SkillTreeQuickAddForm()
        return context


class SkillTreeVersionCreateView(StandardCreateMixin, TitleMixin, PermissionRequiredMixin, CreateView):
    model = SkillTreeVersion
    form_class = SkillTreeVersionForm
    title = "新增技能树版本"
    permission_required = "standards.add_skilltreeversion"
    success_url_name = "standards:tree_detail"


class SkillTreeVersionUpdateView(SkillTreeVersionCreateView, UpdateView):
    title = "编辑技能树版本"
    permission_required = "standards.change_skilltreeversion"


def _tree_for_workbench(tree_pk):
    return get_object_or_404(SkillTreeVersion.objects.select_related("skill_project"), pk=tree_pk)


def _tree_node(tree, node_pk):
    return get_object_or_404(
        SkillTreeNode.objects.select_related("skill", "technical_domain", "tree_version"),
        pk=node_pk,
        tree_version=tree,
    )


def _tree_descendant_count(tree, node):
    children_by_parent = {}
    for child_id, parent_id in SkillTreeNode.objects.filter(tree_version=tree).values_list("pk", "parent_id"):
        children_by_parent.setdefault(parent_id, []).append(child_id)
    count = 0
    stack = list(children_by_parent.get(node.pk, ()))
    while stack:
        current = stack.pop()
        count += 1
        stack.extend(children_by_parent.get(current, ()))
    return count


def _render_tree_panel(request, tree, *, created_node_id=None):
    response = render(
        request,
        "standards/partials/skill_tree_panel.html",
        {
            "tree": tree,
            "tree_domains": skill_tree_structure(tree_version=tree, user=request.user),
            "quick_add_form": SkillTreeQuickAddForm(),
        },
    )
    if created_node_id is not None:
        response.headers["HX-Trigger-After-Swap"] = json.dumps({"skillTreeNodeCreated": {"nodeId": created_node_id}})
    return response


def skill_tree_panel(request, tree_pk):
    if not request.user.has_perm("standards.view_skilltreeversion"):
        raise PermissionDenied
    return _render_tree_panel(request, _tree_for_workbench(tree_pk))


def _quick_add_context(*, tree, domain, parent, form, candidates=()):
    return {
        "tree": tree,
        "domain": domain,
        "parent": parent,
        "quick_add_form": form,
        "candidates": candidates,
    }


def _tree_candidates(*, tree, domain, query):
    candidates = find_skill_candidates(skill_project=tree.skill_project, query=query)
    existing_by_skill = {
        node.skill_id: node
        for node in SkillTreeNode.objects.filter(
            tree_version=tree,
            skill_id__in=[candidate.pk for candidate in candidates],
        ).select_related("skill", "parent__skill")
    }
    for candidate in candidates:
        candidate.existing_tree_node = existing_by_skill.get(candidate.pk)
        candidate.can_attach_to_domain = (
            candidate.is_active
            and candidate.existing_tree_node is None
            and (
                candidate.primary_domain_id == domain.pk
                or any(item.pk == domain.pk for item in candidate.related_domains.all())
            )
        )
    return candidates


@require_POST
def skill_tree_quick_add(request, tree_pk, domain_pk, parent_pk=None):
    tree = _tree_for_workbench(tree_pk)
    domain = get_object_or_404(TechnicalDomain, pk=domain_pk, skill_project=tree.skill_project)
    parent = _tree_node(tree, parent_pk) if parent_pk is not None else None
    if parent is not None and parent.technical_domain_id != domain.pk:
        raise Http404
    if not can_manage_domain(request.user, domain, permission="standards.add_skilltreenode"):
        raise PermissionDenied
    form = SkillTreeQuickAddForm(request.POST)
    candidates = []
    if form.is_valid():
        try:
            if skill_id := form.cleaned_data.get("existing_skill_id"):
                skill = get_object_or_404(Skill, pk=skill_id, skill_project=tree.skill_project)
                node = attach_existing_skill_to_tree(
                    tree_version=tree,
                    technical_domain=domain,
                    parent=parent,
                    skill=skill,
                    actor=request.user,
                )
            else:
                node = create_skill_in_tree(
                    tree_version=tree,
                    technical_domain=domain,
                    parent=parent,
                    name=form.cleaned_data["name"],
                    description=form.cleaned_data.get("description", ""),
                    confirm_distinct=form.cleaned_data.get("confirm_distinct", False),
                    actor=request.user,
                )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            response = _render_tree_panel(request, tree, created_node_id=node.pk)
            response.headers["HX-Retarget"] = "#skill-tree-panel"
            response.headers["HX-Reswap"] = "outerHTML"
            return response
    if form.data.get("name"):
        candidates = _tree_candidates(tree=tree, domain=domain, query=form.data["name"])
    return render(
        request,
        "standards/partials/skill_tree_quick_add.html",
        _quick_add_context(tree=tree, domain=domain, parent=parent, form=form, candidates=candidates),
    )


def skill_tree_candidates(request, tree_pk, domain_pk, parent_pk=None):
    tree = _tree_for_workbench(tree_pk)
    domain = get_object_or_404(TechnicalDomain, pk=domain_pk, skill_project=tree.skill_project)
    parent = _tree_node(tree, parent_pk) if parent_pk is not None else None
    if parent is not None and parent.technical_domain_id != domain.pk:
        raise Http404
    if not can_manage_domain(request.user, domain, permission="standards.add_skilltreenode"):
        raise PermissionDenied
    query = request.GET.get("name", "")
    candidates = _tree_candidates(tree=tree, domain=domain, query=query)
    return render(
        request,
        "standards/partials/skill_tree_candidates.html",
        _quick_add_context(
            tree=tree,
            domain=domain,
            parent=parent,
            form=SkillTreeQuickAddForm(initial={"name": query}),
            candidates=candidates,
        ),
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
        user=request.user,
    )
    form.fields["target_domain"].widget.attrs.update(
        {
            "hx-get": reverse("standards:tree_node_move", args=[tree.pk, node.pk]),
            "hx-target": "#skill-tree-dialog",
            "hx-trigger": "change",
            "hx-include": "this",
        }
    )
    if request.method == "POST" and form.is_valid():
        parent_id = form.cleaned_data.get("new_parent")
        new_parent = _tree_node(tree, int(parent_id)) if parent_id else None
        try:
            move_skill_tree_node(
                node=node,
                new_parent=new_parent,
                target_domain=form.cleaned_data["target_domain"],
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
    form = SkillTreeRemoveForm(request.POST or None)
    descendant_count = _tree_descendant_count(tree, node)
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
            "descendant_count": descendant_count,
            "subtree_count": descendant_count + 1,
        },
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


class WSOSVersionCreateView(StandardCreateMixin, TitleMixin, PermissionRequiredMixin, CreateView):
    model = WSOSVersion
    form_class = WSOSVersionForm
    title = "新增 WSOS 版本"
    permission_required = "standards.add_wsosversion"
    success_url_name = "standards:wsos_detail"


class WSOSVersionUpdateView(WSOSVersionCreateView, UpdateView):
    title = "编辑 WSOS 版本"
    permission_required = "standards.change_wsosversion"
