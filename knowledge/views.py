from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, FormView, UpdateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .forms import KnowledgeEvidenceForm, KnowledgeEvidenceRejectForm, KnowledgeEvidenceSkillMapForm
from .models import KnowledgeEvidence, KnowledgeEvidenceSkillMap
from .selectors import get_unmapped_evidences
from .tables import KnowledgeEvidenceSkillMapTable, KnowledgeEvidenceTable


class KnowledgeEvidenceListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = KnowledgeEvidence
    table_class = KnowledgeEvidenceTable
    template_name = "knowledge/evidence_list.html"
    title = "考点证据"
    title_icon = "icon-[tabler--bulb]"
    permission_required = "knowledge.view_knowledgeevidence"

    def get_queryset(self):
        return super().get_queryset().select_related("skill_project", "event_module", "capability_domain")


class UnmappedEvidenceListView(KnowledgeEvidenceListView):
    title = "未映射考点"

    def get_queryset(self):
        return get_unmapped_evidences()


class KnowledgeEvidenceDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = KnowledgeEvidence
    template_name = "knowledge/evidence_detail.html"
    context_object_name = "evidence"
    title = "{title}"
    title_icon = "icon-[tabler--bulb]"
    permission_required = "knowledge.view_knowledgeevidence"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["mapping_table"] = KnowledgeEvidenceSkillMapTable(self.object.skill_mappings.select_related("skill_node"))
        return context


class KnowledgeEvidenceCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = KnowledgeEvidence
    form_class = KnowledgeEvidenceForm
    template_name = "common/form.html"
    permission_required = "knowledge.add_knowledgeevidence"
    title = "新增考点证据"
    title_icon = "icon-[tabler--plus]"

    def form_valid(self, form):
        if form.instance.created_by_id is None:
            form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("knowledge:evidence_detail", args=[self.object.pk])


class KnowledgeEvidenceUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = KnowledgeEvidence
    form_class = KnowledgeEvidenceForm
    template_name = "common/form.html"
    permission_required = "knowledge.change_knowledgeevidence"
    title = "编辑考点证据"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("knowledge:evidence_detail", args=[self.object.pk])


class KnowledgeEvidenceApproveView(PermissionRequiredMixin, DetailView):
    model = KnowledgeEvidence
    permission_required = "knowledge.change_knowledgeevidence"

    def post(self, request, *args, **kwargs):
        evidence = self.get_object()
        evidence.approve(user=request.user)
        return redirect("knowledge:evidence_detail", pk=evidence.pk)


class KnowledgeEvidenceRejectView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = KnowledgeEvidenceRejectForm
    template_name = "common/form.html"
    permission_required = "knowledge.change_knowledgeevidence"
    title = "拒绝考点证据"
    title_icon = "icon-[tabler--x]"

    def dispatch(self, request, *args, **kwargs):
        self.evidence = KnowledgeEvidence.objects.get(pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            self.evidence.reject(user=self.request.user, note=form.cleaned_data["review_note"])
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("knowledge:evidence_detail", args=[self.evidence.pk])


class KnowledgeEvidenceSkillMapCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = KnowledgeEvidenceSkillMap
    form_class = KnowledgeEvidenceSkillMapForm
    template_name = "common/form.html"
    permission_required = "knowledge.add_knowledgeevidenceskillmap"
    title = "映射技能点"
    title_icon = "icon-[tabler--git-merge]"

    def dispatch(self, request, *args, **kwargs):
        evidence_id = request.GET.get("evidence") or request.POST.get("evidence")
        self.evidence = KnowledgeEvidence.objects.filter(pk=evidence_id).first() if evidence_id else None
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.evidence is not None:
            kwargs["evidence"] = self.evidence
        return kwargs

    def get_success_url(self):
        return reverse("knowledge:evidence_detail", args=[self.object.evidence_id])


class KnowledgeEvidenceSkillMapDeleteView(PermissionRequiredMixin, DeleteView):
    model = KnowledgeEvidenceSkillMap
    permission_required = "knowledge.delete_knowledgeevidenceskillmap"
    template_name = "knowledge/mapping_confirm_delete.html"

    def get_success_url(self):
        return reverse("knowledge:evidence_detail", args=[self.object.evidence_id])

# Create your views here.
