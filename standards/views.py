from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, DetailView, UpdateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin
from knowledge.selectors import get_skill_tree_coverage_rows, get_skill_tree_coverage_summary

from .forms import CapabilityDomainForm, SkillNodeForm, SkillProjectForm, SkillTreeVersionForm
from .models import CapabilityDomain, SkillNode, SkillProject, SkillTreeVersion
from .tables import CapabilityDomainTable, SkillNodeTable, SkillProjectTable, SkillTreeVersionTable


MAINTAIN_PERM = "standards.add_skillproject"


class SkillProjectListView(TitleMixin, LoginRequiredMixin, SingleTableView):
    model = SkillProject
    table_class = SkillProjectTable
    template_name = "standards/project_list.html"
    title = "技能项目"
    title_icon = "icon-[tabler--target-arrow]"


class SkillProjectDetailView(TitleMixin, LoginRequiredMixin, DetailView):
    model = SkillProject
    template_name = "standards/project_detail.html"
    context_object_name = "project"
    title = "{name}"
    title_icon = "icon-[tabler--target-arrow]"


class SkillProjectCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = SkillProject
    form_class = SkillProjectForm
    template_name = "common/form.html"
    permission_required = "standards.add_skillproject"
    title = "新增技能项目"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("standards:project_detail", args=[self.object.pk])


class SkillProjectUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = SkillProject
    form_class = SkillProjectForm
    template_name = "common/form.html"
    permission_required = "standards.change_skillproject"
    title = "编辑技能项目"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("standards:project_detail", args=[self.object.pk])


class CapabilityDomainListView(TitleMixin, LoginRequiredMixin, SingleTableView):
    model = CapabilityDomain
    table_class = CapabilityDomainTable
    template_name = "common/table_page.html"
    title = "能力领域"
    title_icon = "icon-[tabler--category]"


class CapabilityDomainDetailView(TitleMixin, LoginRequiredMixin, DetailView):
    model = CapabilityDomain
    template_name = "standards/domain_detail.html"
    context_object_name = "domain"
    title = "{name}"
    title_icon = "icon-[tabler--category]"


class CapabilityDomainCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = CapabilityDomain
    form_class = CapabilityDomainForm
    template_name = "common/form.html"
    permission_required = "standards.add_capabilitydomain"
    title = "新增能力领域"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("standards:domain_detail", args=[self.object.pk])


class CapabilityDomainUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = CapabilityDomain
    form_class = CapabilityDomainForm
    template_name = "common/form.html"
    permission_required = "standards.change_capabilitydomain"
    title = "编辑能力领域"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("standards:domain_detail", args=[self.object.pk])


class SkillTreeVersionListView(TitleMixin, LoginRequiredMixin, SingleTableView):
    model = SkillTreeVersion
    table_class = SkillTreeVersionTable
    template_name = "common/table_page.html"
    title = "标准技能树版本"
    title_icon = "icon-[tabler--git-branch]"


class SkillTreeVersionDetailView(TitleMixin, LoginRequiredMixin, DetailView):
    model = SkillTreeVersion
    template_name = "standards/tree_detail.html"
    context_object_name = "tree"
    title = "{name}"
    title_icon = "icon-[tabler--git-branch]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["coverage_summary"] = get_skill_tree_coverage_summary(self.object)
        context["coverage_rows"] = get_skill_tree_coverage_rows(self.object)
        return context


class SkillTreeVersionCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = SkillTreeVersion
    form_class = SkillTreeVersionForm
    template_name = "common/form.html"
    permission_required = "standards.add_skilltreeversion"
    title = "新增技能树版本"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("standards:tree_detail", args=[self.object.pk])


class SkillTreeVersionUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = SkillTreeVersion
    form_class = SkillTreeVersionForm
    template_name = "common/form.html"
    permission_required = "standards.change_skilltreeversion"
    title = "编辑技能树版本"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("standards:tree_detail", args=[self.object.pk])


class SkillNodeListView(TitleMixin, LoginRequiredMixin, SingleTableView):
    model = SkillNode
    table_class = SkillNodeTable
    template_name = "common/table_page.html"
    title = "技能节点"
    title_icon = "icon-[tabler--hierarchy]"

    def get_queryset(self):
        return super().get_queryset().select_related("tree_version", "capability_domain", "parent")


class SkillNodeDetailView(TitleMixin, LoginRequiredMixin, DetailView):
    model = SkillNode
    template_name = "standards/node_detail.html"
    context_object_name = "node"
    title = "{name}"
    title_icon = "icon-[tabler--hierarchy]"


class SkillNodeCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = SkillNode
    form_class = SkillNodeForm
    template_name = "common/form.html"
    permission_required = "standards.add_skillnode"
    title = "新增技能节点"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("standards:node_detail", args=[self.object.pk])


class SkillNodeUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = SkillNode
    form_class = SkillNodeForm
    template_name = "common/form.html"
    permission_required = "standards.change_skillnode"
    title = "编辑技能节点"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("standards:node_detail", args=[self.object.pk])

# Create your views here.
