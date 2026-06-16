from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView

from core.utils.mixins import TitleMixin

from assessments.models import AssessmentModule
from competitions.models import CompetitionModule

from .forms import MarkingAspectSkillNodeMapForm, MarkingResultImportForm, MarkingSchemeImportForm
from .models import MarkingAspect, MarkingAspectSkillNodeMap, MarkingScheme


class MarkingSchemeAccessMixin:
    def filter_schemes_for_user(self, queryset):
        user = self.request.user
        if user.is_superuser:
            return queryset

        competition_module_type = ContentType.objects.get_for_model(CompetitionModule, for_concrete_model=False)
        assessment_module_type = ContentType.objects.get_for_model(AssessmentModule, for_concrete_model=False)

        allowed_assessment_modules = AssessmentModule.objects.all()
        if not user.has_perm("assessments.view_all_scores"):
            allowed_assessment_modules = allowed_assessment_modules.filter(
                Q(responsible_coach=user) | Q(assessment__participants=user)
            )

        return queryset.filter(
            Q(target_content_type=competition_module_type)
            | Q(
                target_content_type=assessment_module_type,
                target_object_id__in=allowed_assessment_modules.values("pk"),
            )
        )


class MarkingSchemeListView(MarkingSchemeAccessMixin, TitleMixin, LoginRequiredMixin, ListView):
    model = MarkingScheme
    template_name = "marking/scheme_list.html"
    context_object_name = "schemes"
    paginate_by = 20
    title = "评分归档"
    title_icon = "icon-[tabler--clipboard-list]"

    def get_queryset(self):
        queryset = MarkingScheme.objects.select_related("standard_module__project", "source_import").order_by(
            "-created_at",
            "module_code",
        )
        return self.filter_schemes_for_user(queryset)


class MarkingSchemeDetailView(MarkingSchemeAccessMixin, TitleMixin, LoginRequiredMixin, DetailView):
    model = MarkingScheme
    template_name = "marking/scheme_detail.html"
    context_object_name = "scheme"
    title = "{module_code} - {module_name}"
    title_icon = "icon-[tabler--clipboard-list]"

    def get_queryset(self):
        queryset = MarkingScheme.objects.select_related("standard_module__project", "source_import").prefetch_related(
            "subcriteria__aspects__judgement_options",
            "aspects__skill_node_mappings__skill_node__tree",
        )
        return self.filter_schemes_for_user(queryset)


class MarkingSchemeSourceDownloadView(MarkingSchemeAccessMixin, LoginRequiredMixin, View):
    def get(self, request, pk):
        queryset = self.filter_schemes_for_user(MarkingScheme.objects.select_related("source_import"))
        scheme = get_object_or_404(queryset, pk=pk)
        source_file = scheme.source_import.file
        if not source_file:
            raise Http404("原始评分表文件不存在。")
        filename = scheme.source_import.original_filename or source_file.name.rsplit("/", 1)[-1]
        return FileResponse(source_file.open("rb"), as_attachment=True, filename=filename)


class MarkingSchemeImportView(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, FormView):
    form_class = MarkingSchemeImportForm
    template_name = "marking/import_form.html"
    permission_required = "marking.add_markingschemeimport"
    raise_exception = True
    title = "导入评分表"
    title_icon = "icon-[tabler--file-import]"

    def get_initial(self):
        initial = super().get_initial()
        for key in ("target_type", "competition_module", "assessment_module"):
            value = self.request.GET.get(key)
            if value:
                initial[key] = value
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f"评分表“{self.object}”已导入。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("marking:scheme_detail", args=[self.object.pk])


class MarkingResultImportView(MarkingSchemeAccessMixin, TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, FormView):
    form_class = MarkingResultImportForm
    template_name = "marking/result_import_form.html"
    permission_required = "marking.add_markingresultimport"
    raise_exception = True
    title = "导入 CMP 结果包"
    title_icon = "icon-[tabler--database-import]"

    def dispatch(self, request, *args, **kwargs):
        self.scheme = None
        scheme_id = kwargs.get("scheme_pk")
        if scheme_id:
            queryset = self.filter_schemes_for_user(MarkingScheme.objects.all())
            self.scheme = get_object_or_404(queryset, pk=scheme_id)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["scheme"] = self.scheme
        return kwargs

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, "CMP 结果包已导入。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("marking:scheme_detail", args=[self.object.scheme_id])


class AspectSkillMapCreateView(MarkingSchemeAccessMixin, TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = MarkingAspectSkillNodeMap
    form_class = MarkingAspectSkillNodeMapForm
    template_name = "marking/aspect_mapping_form.html"
    permission_required = "marking.add_markingaspectskillnodemap"
    raise_exception = True
    title = "评分点归类到技能点"
    title_icon = "icon-[tabler--hierarchy]"

    def dispatch(self, request, *args, **kwargs):
        scheme_queryset = self.filter_schemes_for_user(MarkingScheme.objects.all())
        self.aspect = get_object_or_404(
            MarkingAspect.objects.select_related("scheme__standard_module", "subcriterion"),
            scheme__in=scheme_queryset,
            pk=kwargs["aspect_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["aspect"] = self.aspect
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["aspect"] = self.aspect
        context["existing_mappings"] = self.aspect.skill_node_mappings.select_related("skill_node__tree")
        return context

    def form_valid(self, form):
        messages.success(self.request, "评分点技能归类已保存。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("marking:scheme_detail", args=[self.aspect.scheme_id])


class AspectSkillMapDeleteView(MarkingSchemeAccessMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "marking.delete_markingaspectskillnodemap"
    raise_exception = True

    def post(self, request, pk):
        scheme_queryset = self.filter_schemes_for_user(MarkingScheme.objects.all())
        mapping = get_object_or_404(
            MarkingAspectSkillNodeMap.objects.select_related("aspect"),
            aspect__scheme__in=scheme_queryset,
            pk=pk,
        )
        scheme_id = mapping.aspect.scheme_id
        mapping.delete()
        messages.success(request, "评分点技能归类已删除。")
        return redirect("marking:scheme_detail", pk=scheme_id)
