from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, FormView, UpdateView
from django_tables2 import SingleTableView
from assessments.selectors import manageable_assessment_modules_for, visible_assessments_for
from core.utils.mixins import TitleMixin
from .forms import EvidenceSkillMapForm, KnowledgeEvidenceForm, KnowledgeEvidenceRejectForm
from .models import EvidenceSkillMap, KnowledgeEvidence
from .services import approve_evidence, approve_mapping, reject_evidence
from .tables import KnowledgeEvidenceTable


def visible_evidences_for(user):
    queryset = KnowledgeEvidence.objects.all()
    if user.is_superuser:
        return queryset
    return queryset.filter(assessment_module__assessment__in=visible_assessments_for(user)).distinct()


def manageable_evidences_for(user):
    if user.is_superuser:
        return KnowledgeEvidence.objects.all()
    return KnowledgeEvidence.objects.filter(assessment_module__in=manageable_assessment_modules_for(user)).distinct()


class KnowledgeEvidenceListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = KnowledgeEvidence
    table_class = KnowledgeEvidenceTable
    template_name = "evidence/evidence_list.html"
    title = "考点证据"
    permission_required = "evidence.view_knowledgeevidence"

    def get_queryset(self):
        return visible_evidences_for(self.request.user).select_related("skill_project", "assessment_module")


class KnowledgeEvidenceDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = KnowledgeEvidence
    template_name = "evidence/evidence_detail.html"
    context_object_name = "evidence"
    title = "{title}"
    permission_required = "evidence.view_knowledgeevidence"

    def get_queryset(self):
        return visible_evidences_for(self.request.user).prefetch_related("skill_mappings__skill")


class KnowledgeEvidenceCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = KnowledgeEvidence
    form_class = KnowledgeEvidenceForm
    template_name = "common/form.html"
    title = "新增考点证据"
    permission_required = "evidence.add_knowledgeevidence"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.extraction_source = KnowledgeEvidence.ExtractionSource.MANUAL
        module = form.cleaned_data.get("assessment_module")
        direct = self.request.user.is_superuser or (
            module and manageable_assessment_modules_for(self.request.user).filter(pk=module.pk).exists()
        )
        form.instance.review_status = (
            KnowledgeEvidence.ReviewStatus.APPROVED if direct else KnowledgeEvidence.ReviewStatus.PENDING
        )
        if direct:
            form.instance.reviewed_by = self.request.user
            form.instance.reviewed_at = timezone.now()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("evidence:evidence_detail", args=[self.object.pk])


class KnowledgeEvidenceUpdateView(KnowledgeEvidenceCreateView, UpdateView):
    title = "编辑考点证据"
    permission_required = "evidence.change_knowledgeevidence"

    def get_queryset(self):
        return manageable_evidences_for(self.request.user)


class KnowledgeEvidenceApproveView(PermissionRequiredMixin, DetailView):
    model = KnowledgeEvidence
    permission_required = "evidence.change_knowledgeevidence"

    def get_queryset(self):
        return manageable_evidences_for(self.request.user)

    def post(self, request, *args, **kwargs):
        approve_evidence(self.get_object(), user=request.user)
        messages.success(request, "考点证据已批准。")
        return redirect("evidence:evidence_detail", pk=self.kwargs["pk"])


class KnowledgeEvidenceRejectView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = KnowledgeEvidenceRejectForm
    template_name = "common/form.html"
    title = "拒绝考点证据"
    permission_required = "evidence.change_knowledgeevidence"

    def form_valid(self, form):
        evidence = manageable_evidences_for(self.request.user).get(pk=self.kwargs["pk"])
        reject_evidence(evidence, user=self.request.user, note=form.cleaned_data["review_note"])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("evidence:evidence_detail", args=[self.kwargs["pk"]])


class EvidenceSkillMapCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = EvidenceSkillMap
    form_class = EvidenceSkillMapForm
    template_name = "common/form.html"
    title = "映射技能"
    permission_required = "evidence.add_evidenceskillmap"

    def get_evidence(self):
        return manageable_evidences_for(self.request.user).get(pk=self.kwargs["evidence_pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["evidence"] = self.get_evidence()
        return kwargs

    def form_valid(self, form):
        form.instance.review_status = KnowledgeEvidence.ReviewStatus.APPROVED
        form.instance.reviewed_by = self.request.user
        response = super().form_valid(form)
        approve_mapping(self.object, user=self.request.user)
        return response

    def get_success_url(self):
        return reverse("evidence:evidence_detail", args=[self.object.evidence_id])


class EvidenceSkillMapDeleteView(PermissionRequiredMixin, DeleteView):
    model = EvidenceSkillMap
    permission_required = "evidence.delete_evidenceskillmap"
    template_name = "evidence/mapping_confirm_delete.html"

    def get_queryset(self):
        return EvidenceSkillMap.objects.filter(evidence__in=manageable_evidences_for(self.request.user))

    def get_success_url(self):
        return reverse("evidence:evidence_detail", args=[self.object.evidence_id])
