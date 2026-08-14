from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, DetailView, UpdateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .forms import ExamPaperForm, ExamRequirementForm
from .models import ExamPaper, ExamRequirement
from .services import create_evidence_for_requirement
from .tables import ExamPaperTable, ExamRequirementTable


class ExamPaperListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = ExamPaper
    table_class = ExamPaperTable
    template_name = "examcontent/paper_list.html"
    title = "试题"
    title_icon = "icon-[tabler--file-description]"
    permission_required = "examcontent.view_exampaper"


class ExamPaperDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = ExamPaper
    template_name = "examcontent/paper_detail.html"
    context_object_name = "paper"
    title = "{title}"
    title_icon = "icon-[tabler--file-description]"
    permission_required = "examcontent.view_exampaper"


class ExamPaperCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ExamPaper
    form_class = ExamPaperForm
    template_name = "common/form.html"
    permission_required = "examcontent.add_exampaper"
    title = "新增试题"
    title_icon = "icon-[tabler--plus]"

    def form_valid(self, form):
        if form.instance.created_by_id is None:
            form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("examcontent:paper_detail", args=[self.object.pk])


class ExamPaperUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = ExamPaper
    form_class = ExamPaperForm
    template_name = "common/form.html"
    permission_required = "examcontent.change_exampaper"
    title = "编辑试题"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("examcontent:paper_detail", args=[self.object.pk])


class ExamRequirementListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = ExamRequirement
    table_class = ExamRequirementTable
    template_name = "common/table_page.html"
    title = "试题要求"
    title_icon = "icon-[tabler--list-details]"
    permission_required = "examcontent.view_examrequirement"


class ExamRequirementDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = ExamRequirement
    template_name = "examcontent/requirement_detail.html"
    context_object_name = "requirement"
    title = "{title}"
    title_icon = "icon-[tabler--list-details]"
    permission_required = "examcontent.view_examrequirement"


class ExamRequirementCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ExamRequirement
    form_class = ExamRequirementForm
    template_name = "common/form.html"
    permission_required = "examcontent.add_examrequirement"
    title = "新增试题要求"
    title_icon = "icon-[tabler--plus]"

    def form_valid(self, form):
        response = super().form_valid(form)
        create_evidence_for_requirement(self.object, created_by=self.request.user)
        return response

    def get_success_url(self):
        return reverse("examcontent:requirement_detail", args=[self.object.pk])


class ExamRequirementUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = ExamRequirement
    form_class = ExamRequirementForm
    template_name = "common/form.html"
    permission_required = "examcontent.change_examrequirement"
    title = "编辑试题要求"
    title_icon = "icon-[tabler--edit]"

    def form_valid(self, form):
        response = super().form_valid(form)
        create_evidence_for_requirement(self.object, created_by=self.request.user)
        return response

    def get_success_url(self):
        return reverse("examcontent:requirement_detail", args=[self.object.pk])

# Create your views here.
