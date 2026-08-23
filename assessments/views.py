from pathlib import Path
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import FileResponse, Http404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, UpdateView
from django_tables2 import SingleTableView
from core.utils.mixins import TitleMixin
from .forms import AssessmentDocumentForm, AssessmentForm, AssessmentModuleForm, AssessmentParticipantForm
from .models import Assessment, AssessmentDocument, AssessmentModule, AssessmentParticipant
from .selectors import manageable_assessment_modules_for, visible_assessments_for, visible_documents_for
from .tables import AssessmentModuleTable, AssessmentTable


class AssessmentListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = Assessment
    table_class = AssessmentTable
    template_name = "assessments/assessment_list.html"
    title = "竞赛与考核"
    permission_required = "assessments.view_assessment"

    def get_queryset(self):
        queryset = visible_assessments_for(self.request.user).select_related("skill_project", "series", "level")
        if value := self.request.GET.get("type"):
            queryset = queryset.filter(assessment_type=value)
        if value := self.request.GET.get("status"):
            queryset = queryset.filter(status=value)
        if value := self.request.GET.get("q"):
            queryset = queryset.filter(name__icontains=value)
        return queryset


class AssessmentDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = Assessment
    template_name = "assessments/assessment_detail.html"
    context_object_name = "assessment"
    title = "{name}"
    permission_required = "assessments.view_assessment"

    def get_queryset(self):
        return visible_assessments_for(self.request.user).prefetch_related("modules", "participants", "documents")


class AssessmentCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = Assessment
    form_class = AssessmentForm
    template_name = "common/form.html"
    extra_context = {"grid_class": "grid gap-4 md:grid-cols-2"}
    title = "新增竞赛与考核"
    permission_required = "assessments.add_assessment"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assessments:assessment_detail", args=[self.object.pk])


class AssessmentUpdateView(AssessmentCreateView, UpdateView):
    title = "编辑竞赛与考核"
    permission_required = "assessments.change_assessment"

    def get_queryset(self):
        if not self.request.user.is_superuser:
            raise Http404
        return Assessment.objects.all()


class AssessmentModuleListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = AssessmentModule
    table_class = AssessmentModuleTable
    template_name = "assessments/module_list.html"
    title = "评测模块"
    permission_required = "assessments.view_assessmentmodule"

    def get_queryset(self):
        return AssessmentModule.objects.filter(
            assessment__in=visible_assessments_for(self.request.user)
        ).select_related("assessment")


class AssessmentModuleDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = AssessmentModule
    template_name = "assessments/module_detail.html"
    context_object_name = "module"
    title = "{name}"
    permission_required = "assessments.view_assessmentmodule"

    def get_queryset(self):
        return AssessmentModule.objects.filter(
            assessment__in=visible_assessments_for(self.request.user)
        ).prefetch_related("domain_mappings__technical_domain", "coach_assignments__user", "documents", "evidences")


class AssessmentModuleCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = AssessmentModule
    form_class = AssessmentModuleForm
    template_name = "common/form.html"
    title = "新增评测模块"
    permission_required = "assessments.add_assessmentmodule"

    def get_success_url(self):
        return reverse("assessments:module_detail", args=[self.object.pk])


class AssessmentModuleUpdateView(AssessmentModuleCreateView, UpdateView):
    title = "编辑评测模块"
    permission_required = "assessments.change_assessmentmodule"

    def get_queryset(self):
        return manageable_assessment_modules_for(self.request.user)


class AssessmentParticipantDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = AssessmentParticipant
    template_name = "assessments/participant_detail.html"
    context_object_name = "participant"
    title = "{display_name}"
    permission_required = "assessments.view_assessmentparticipant"


class AssessmentParticipantCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = AssessmentParticipant
    form_class = AssessmentParticipantForm
    template_name = "common/form.html"
    extra_context = {"grid_class": "grid gap-4 md:grid-cols-2"}
    title = "新增参与人员"
    permission_required = "assessments.add_assessmentparticipant"

    def get_success_url(self):
        return reverse("assessments:participant_detail", args=[self.object.pk])


class AssessmentDocumentCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = AssessmentDocument
    form_class = AssessmentDocumentForm
    template_name = "common/form.html"
    title = "上传评测资料"
    permission_required = "assessments.add_assessmentdocument"

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        form.instance.original_filename = Path(form.cleaned_data["file"].name).name
        return super().form_valid(form)

    def get_success_url(self):
        return (
            reverse("assessments:module_detail", args=[self.object.module_id])
            if self.object.module_id
            else reverse("assessments:assessment_detail", args=[self.object.assessment_id])
        )


class AssessmentDocumentDownloadView(PermissionRequiredMixin, DetailView):
    model = AssessmentDocument
    permission_required = "assessments.view_assessmentdocument"

    def get_queryset(self):
        return visible_documents_for(self.request.user)

    def get(self, request, *args, **kwargs):
        document = self.get_object()
        response = FileResponse(document.file.open("rb"), as_attachment=True, filename=document.filename)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
