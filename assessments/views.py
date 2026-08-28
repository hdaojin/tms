from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, FormView, UpdateView, View
from django_tables2 import SingleTableView

from accounts.services.users import get_user_display_name
from core.file_preview import (
    FilePreviewMetadata,
    build_download_response,
    build_file_preview_descriptor,
    build_inline_preview_response,
)
from core.utils.mixins import TitleMixin
from evidence.selectors import visible_evidences_for
from scoring.selectors import (
    assessment_scoring_summaries,
    scoring_modules_in_scope_for,
    scoring_results_visible_to,
    scoring_schemes_in_scope_for,
)
from standards.selectors import assessment_skill_performance

from .forms import (
    AssessmentAwardForm,
    AssessmentDocumentForm,
    AssessmentFinalResultForm,
    AssessmentFinalScoreFormSet,
    AssessmentForm,
    AssessmentUpdateForm,
    AssessmentModuleForm,
    AssessmentParticipantForm,
    CompetitionPersonForm,
    CompetitionRoleForm,
)
from .models import (
    Assessment,
    AssessmentAward,
    AssessmentDocument,
    AssessmentFinalResult,
    AssessmentModule,
    AssessmentParticipant,
    CompetitionPerson,
    CompetitionRole,
)
from .selectors import (
    calculated_final_result_preview,
    assessment_modules_in_scope_for,
    manageable_assessment_modules_for,
    manageable_assessments_for,
    manageable_final_results_for,
    visible_assessment_modules_for,
    visible_assessment_participants_for,
    visible_assessments_for,
    visible_documents_for,
    visible_final_results_for,
)
from .services import (
    confirm_final_result,
    create_assessment_award,
    generate_final_results,
    publish_final_results,
    transition_assessment,
    update_final_result_details,
)
from .tables import AssessmentModuleTable, AssessmentTable, CompetitionPersonTable, CompetitionRoleTable


WORKSPACE_DOCUMENT_KINDS = {
    ".pdf": "pdf",
    ".doc": "word",
    ".docx": "word",
    ".xls": "excel",
    ".xlsx": "excel",
    ".csv": "excel",
    ".zip": "archive",
    ".rar": "archive",
    ".7z": "archive",
    ".tar": "archive",
    ".gz": "archive",
}


class AssessmentListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = Assessment
    table_class = AssessmentTable
    template_name = "assessments/assessment_list.html"
    title = "竞赛与考核"
    permission_required = "assessments.view_assessment"

    def get_queryset(self):
        queryset = visible_assessments_for(self.request.user).select_related(
            "skill_project", "series", "level", "assessment_type"
        )
        if value := self.request.GET.get("type"):
            queryset = queryset.filter(assessment_type__code=value)
        if value := self.request.GET.get("status"):
            queryset = queryset.filter(status=value)
        if value := self.request.GET.get("q"):
            queryset = queryset.filter(name__icontains=value)
        return queryset


class CompetitionPersonListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = CompetitionPerson
    table_class = CompetitionPersonTable
    template_name = "assessments/competition_person_list.html"
    title = "长期赛事人员"
    title_icon = "icon-[tabler--address-book]"
    permission_required = "assessments.view_competitionperson"

    def get_queryset(self):
        queryset = super().get_queryset()
        if value := self.request.GET.get("q"):
            queryset = queryset.filter(name__icontains=value)
        return queryset


class CompetitionPersonCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = CompetitionPerson
    form_class = CompetitionPersonForm
    template_name = "common/form.html"
    title = "新增长期赛事人员"
    title_icon = "icon-[tabler--user-plus]"
    permission_required = "assessments.add_competitionperson"

    def get_success_url(self):
        return reverse("assessments:competition_person_list")


class CompetitionPersonUpdateView(CompetitionPersonCreateView, UpdateView):
    title = "编辑长期赛事人员"
    permission_required = "assessments.change_competitionperson"


class CompetitionRoleListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = CompetitionRole
    table_class = CompetitionRoleTable
    template_name = "assessments/competition_role_list.html"
    title = "赛事角色配置"
    title_icon = "icon-[tabler--user-cog]"
    permission_required = "assessments.view_competitionrole"


class CompetitionRoleCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = CompetitionRole
    form_class = CompetitionRoleForm
    template_name = "common/form.html"
    title = "新增赛事角色"
    title_icon = "icon-[tabler--user-plus]"
    permission_required = "assessments.add_competitionrole"

    def get_success_url(self):
        return reverse("assessments:competition_role_list")


class CompetitionRoleUpdateView(CompetitionRoleCreateView, UpdateView):
    title = "编辑赛事角色"
    permission_required = "assessments.change_competitionrole"


class AssessmentDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = Assessment
    template_name = "assessments/assessment_detail.html"
    context_object_name = "assessment"
    title = "{name}"
    permission_required = "assessments.view_assessment"

    workspace_tabs = (
        ("overview", "概览", "icon-[tabler--layout-dashboard]"),
        ("modules", "模块与资料", "icon-[tabler--box]"),
        ("people", "人员", "icon-[tabler--users]"),
        ("scoring", "评分", "icon-[tabler--scoreboard]"),
        ("results", "最终结果", "icon-[tabler--trophy]"),
        ("evidence", "考点与技能", "icon-[tabler--target-arrow]"),
        ("analysis", "分析", "icon-[tabler--chart-bar]"),
    )
    lifecycle_actions = {
        Assessment.Status.DRAFT: (("publish", "发布"), ("cancel", "取消")),
        Assessment.Status.PUBLISHED: (("start", "启动"), ("cancel", "取消")),
        Assessment.Status.ACTIVE: (("complete", "完成"), ("cancel", "取消")),
        Assessment.Status.COMPLETED: (("archive", "归档"),),
    }

    def get_queryset(self):
        modules = visible_assessment_modules_for(self.request.user).select_related("assessment").prefetch_related(
            "domain_mappings__technical_domain",
            "coach_assignments__user",
        )
        participants = visible_assessment_participants_for(self.request.user).select_related(
            "role",
            "user",
            "competition_person",
        )
        documents = (
            visible_documents_for(self.request.user)
            .select_related("module", "uploaded_by")
            .order_by("-created_at", "-pk")
        )
        return visible_assessments_for(self.request.user).select_related(
            "skill_project",
            "series",
            "level",
            "created_by",
        ).prefetch_related(
            Prefetch("modules", queryset=modules),
            Prefetch("participants", queryset=participants),
            Prefetch("documents", queryset=documents),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab_keys = {item[0] for item in self.workspace_tabs}
        active_tab = self.request.GET.get("tab", "overview")
        if active_tab not in tab_keys:
            active_tab = "overview"
        base_url = reverse("assessments:assessment_detail", args=[self.object.pk])
        context["workspace_tabs"] = [
            {
                "label": label,
                "href": f"{base_url}?tab={key}",
                "active": key == active_tab,
                "icon": icon,
            }
            for key, label, icon in self.workspace_tabs
        ]
        context["active_tab"] = active_tab
        context["tab_template"] = f"assessments/workspace/{active_tab}.html"

        modules = list(self.object.modules.all())
        participants = list(self.object.participants.all())
        documents = list(self.object.documents.all())
        documents_by_module = {}
        for document in documents:
            if active_tab == "modules":
                document.workspace_file_kind = WORKSPACE_DOCUMENT_KINDS.get(
                    Path(document.filename).suffix.lower(),
                    "file",
                )
                try:
                    document.workspace_file_size = document.file.size
                except Exception:
                    # 历史记录的实体文件可能已缺失，列表页仍应正常显示其余元数据。
                    document.workspace_file_size = None
            documents_by_module.setdefault(document.module_id, []).append(document)
        manageable_module_ids = set(
            manageable_assessment_modules_for(self.request.user, AssessmentModule.objects.filter(assessment=self.object))
            .values_list("pk", flat=True)
        )
        for module in modules:
            module.workspace_documents = documents_by_module.get(module.pk, [])
            module.can_manage = module.pk in manageable_module_ids

        can_manage_assessment = manageable_assessments_for(
            self.request.user,
            Assessment.objects.filter(pk=self.object.pk),
        ).exists()
        context.update(
            {
                "workspace_modules": modules,
                "workspace_participants": participants,
                "general_documents": documents_by_module.get(None, []),
                "competitor_count": sum(
                    participant.role.category == "competitor" for participant in participants
                ),
                "can_manage_assessment": can_manage_assessment,
                "available_lifecycle_actions": self.lifecycle_actions.get(self.object.status, ())
                if can_manage_assessment
                else (),
            }
        )

        scoring_tabs = {"modules", "scoring", "analysis"}
        schemes = (
            list(
                scoring_schemes_in_scope_for(self.request.user)
                .filter(assessment_module__in=modules)
                .prefetch_related("aspects")
            )
            if active_tab in scoring_tabs
            else []
        )
        schemes_by_module = {scheme.assessment_module_id: scheme for scheme in schemes}
        importable_module_ids = set()
        if active_tab == "modules" and self.request.user.has_perm("scoring.add_scoringscheme"):
            importable_module_ids = set(
                scoring_modules_in_scope_for(
                    self.request.user,
                    "scoring.add_scoringscheme",
                    AssessmentModule.objects.filter(pk__in=[module.pk for module in modules]),
                ).values_list("pk", flat=True)
            )
        realtime_module_ids = set()
        if active_tab in scoring_tabs and self.request.user.has_perm("scoring.view_all_scoringresult"):
            realtime_module_ids = set(
                scoring_modules_in_scope_for(
                    self.request.user,
                    "scoring.view_scoringresult",
                    AssessmentModule.objects.filter(pk__in=[module.pk for module in modules]),
                ).values_list("pk", flat=True)
            )
        summary_schemes = [scheme for scheme in schemes if scheme.assessment_module_id in realtime_module_ids]
        summaries = assessment_scoring_summaries(self.object, summary_schemes) if summary_schemes else {}
        for module in modules:
            module.workspace_scheme = schemes_by_module.get(module.pk)
            module.scoring_summary = summaries.get(module.pk)
            module.can_import_scheme = module.pk in importable_module_ids
            module.can_open_online_scoring = bool(
                module.workspace_scheme and module.pk in realtime_module_ids
            )
        context["scoring_schemes"] = schemes

        context["workspace_evidences"] = (
            list(
                visible_evidences_for(self.request.user)
                .filter(assessment_module__in=modules)
                .select_related("assessment_module", "scoring_aspect")
                .prefetch_related("skill_mappings__skill")
            )
            if active_tab == "evidence"
            else []
        )
        can_view_skill_analysis = bool(
            active_tab == "analysis"
            and self.request.user.has_perm("scoring.view_scoringresult")
            and self.request.user.has_perm("scoring.view_all_scoringresult")
            and self.request.user.has_perm("evidence.view_knowledgeevidence")
        )
        analysis_modules = []
        if can_view_skill_analysis:
            evidence_module_ids = set(
                assessment_modules_in_scope_for(
                    self.request.user,
                    "evidence.view_knowledgeevidence",
                    AssessmentModule.objects.filter(pk__in=[module.pk for module in modules]),
                ).values_list("pk", flat=True)
            )
            analysis_module_ids = realtime_module_ids & evidence_module_ids
            analysis_modules = [module for module in modules if module.pk in analysis_module_ids]
        analysis_evidences = visible_evidences_for(self.request.user).filter(assessment_module__in=analysis_modules)
        context.update(
            {
                "can_view_skill_analysis": can_view_skill_analysis,
                "can_open_skill_detail": self.request.user.has_perm("standards.view_skill"),
                "assessment_skill_performance": assessment_skill_performance(
                    self.object,
                    modules=analysis_modules,
                    results=scoring_results_visible_to(self.request.user),
                    evidences=analysis_evidences,
                )
                if can_view_skill_analysis
                else [],
            }
        )
        can_manage_results = bool(
            can_manage_assessment and self.request.user.has_perm("assessments.change_assessmentfinalresult")
        )
        context["workspace_final_results"] = (
            visible_final_results_for(self.request.user, self.object)
            .select_related("participant", "confirmed_by")
            .prefetch_related("scores", "award_links__award")
            if active_tab == "results"
            else AssessmentFinalResult.objects.none()
        )
        context["calculated_final_results"] = (
            calculated_final_result_preview(self.object)
            if active_tab == "results" and can_manage_results
            else []
        )
        context["assessment_awards"] = (
            self.object.awards.all() if active_tab == "results" and can_manage_results else AssessmentAward.objects.none()
        )
        context.update(
            {
                "can_manage_results": can_manage_results,
                "can_generate_final_results": bool(
                    can_manage_results
                    and self.request.user.has_perm("assessments.add_assessmentfinalresult")
                    and self.object.status == Assessment.Status.COMPLETED
                    and self.object.results_published_at is None
                ),
                "can_publish_final_results": bool(
                    can_manage_results
                    and self.object.status == Assessment.Status.COMPLETED
                    and self.object.results_published_at is None
                ),
                "can_create_award": bool(
                    can_manage_results
                    and self.request.user.has_perm("assessments.add_assessmentaward")
                    and self.object.results_published_at is None
                ),
            }
        )
        return context


class AssessmentCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = Assessment
    form_class = AssessmentForm
    template_name = "common/form.html"
    title = "新增竞赛与考核"
    permission_required = "assessments.add_assessment"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("assessments:assessment_detail", args=[self.object.pk])


class AssessmentUpdateView(AssessmentCreateView, UpdateView):
    form_class = AssessmentUpdateForm
    title = "编辑竞赛与考核"
    permission_required = "assessments.change_assessment"

    def get_queryset(self):
        return manageable_assessments_for(self.request.user)


class AssessmentLifecycleActionView(PermissionRequiredMixin, View):
    permission_required = "assessments.change_assessment"

    def post(self, request, *args, **kwargs):
        assessment = get_object_or_404(manageable_assessments_for(request.user), pk=kwargs["pk"])
        try:
            transition_assessment(assessment, kwargs["action"], request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "竞赛或考核状态已更新。")
        return redirect("assessments:assessment_detail", pk=assessment.pk)


class AssessmentFinalResultsGenerateView(PermissionRequiredMixin, View):
    permission_required = (
        "assessments.add_assessmentfinalresult",
        "assessments.change_assessmentfinalresult",
    )

    def post(self, request, *args, **kwargs):
        assessment = get_object_or_404(manageable_assessments_for(request.user), pk=kwargs["pk"])
        try:
            summary = generate_final_results(assessment, request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(
                request,
                f"最终结果已生成：新增 {summary['created_count']}，更新 {summary['updated_count']}，"
                f"保留已确认 {summary['skipped_official_count']}。",
            )
        return redirect(f"{reverse('assessments:assessment_detail', args=[assessment.pk])}?tab=results")


class AssessmentFinalResultConfirmView(PermissionRequiredMixin, View):
    permission_required = "assessments.change_assessmentfinalresult"

    def post(self, request, *args, **kwargs):
        final_result = get_object_or_404(manageable_final_results_for(request.user), pk=kwargs["pk"])
        assessment_id = final_result.participant.assessment_id
        try:
            confirm_final_result(final_result, request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"{final_result.participant.display_name} 的最终结果已确认。")
        return redirect(f"{reverse('assessments:assessment_detail', args=[assessment_id])}?tab=results")


class AssessmentResultsPublishView(PermissionRequiredMixin, View):
    permission_required = (
        "assessments.change_assessment",
        "assessments.change_assessmentfinalresult",
    )

    def post(self, request, *args, **kwargs):
        assessment = get_object_or_404(manageable_assessments_for(request.user), pk=kwargs["pk"])
        try:
            publish_final_results(assessment, request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "最终成绩已发布，选手现在可以查看自己的正式结果。")
        return redirect(f"{reverse('assessments:assessment_detail', args=[assessment.pk])}?tab=results")


class AssessmentFinalResultUpdateView(TitleMixin, PermissionRequiredMixin, View):
    permission_required = "assessments.change_assessmentfinalresult"
    template_name = "assessments/final_result_form.html"
    title = "编辑最终结果"
    title_icon = "icon-[tabler--trophy]"

    def get_object(self):
        return get_object_or_404(
            manageable_final_results_for(self.request.user).select_related("participant", "participant__assessment"),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        final_result = self.get_object()
        return self.render_forms(
            final_result,
            AssessmentFinalResultForm(instance=final_result),
            AssessmentFinalScoreFormSet(instance=final_result),
        )

    def post(self, request, *args, **kwargs):
        final_result = self.get_object()
        form = AssessmentFinalResultForm(request.POST, instance=final_result)
        score_formset = AssessmentFinalScoreFormSet(request.POST, instance=final_result)
        if form.is_valid() and score_formset.is_valid():
            score_rows = []
            for score_form in score_formset.forms:
                cleaned = score_form.cleaned_data
                if not cleaned:
                    continue
                if cleaned.get("DELETE") and not score_form.instance.pk:
                    continue
                score_rows.append(
                    {
                        "score_id": score_form.instance.pk,
                        "delete": cleaned.get("DELETE", False),
                        "score_type": cleaned.get("score_type"),
                        "label": cleaned.get("label"),
                        "value": cleaned.get("value"),
                        "max_value": cleaned.get("max_value"),
                        "order": cleaned.get("order"),
                    }
                )
            try:
                update_final_result_details(
                    final_result,
                    request.user,
                    rank=form.cleaned_data["rank"],
                    notes=form.cleaned_data["notes"],
                    awards=form.cleaned_data["awards"],
                    score_rows=score_rows,
                )
            except ValidationError as exc:
                form.add_error(None, exc.messages)
            else:
                messages.success(request, "最终结果已保存；如内容发生变化，请重新确认。")
                return redirect(
                    f"{reverse('assessments:assessment_detail', args=[final_result.participant.assessment_id])}"
                    "?tab=results"
                )
        return self.render_forms(final_result, form, score_formset)

    def render_forms(self, final_result, form, score_formset):
        return render(
            self.request,
            self.template_name,
            {
                "title": self.title,
                "title_icon": self.title_icon,
                "final_result": final_result,
                "form": form,
                "score_formset": score_formset,
            },
        )


class AssessmentAwardCreateView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = AssessmentAwardForm
    template_name = "common/form.html"
    permission_required = "assessments.add_assessmentaward"
    title = "新增奖项"
    title_icon = "icon-[tabler--award]"

    def get_assessment(self):
        return get_object_or_404(manageable_assessments_for(self.request.user), pk=self.kwargs["pk"])

    def form_valid(self, form):
        assessment = self.get_assessment()
        try:
            create_assessment_award(assessment, self.request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc.messages)
            return self.form_invalid(form)
        messages.success(self.request, "奖项已创建。")
        return super().form_valid(form)

    def get_success_url(self):
        return f"{reverse('assessments:assessment_detail', args=[self.kwargs['pk']])}?tab=results"


class AssessmentModuleListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = AssessmentModule
    table_class = AssessmentModuleTable
    template_name = "assessments/module_list.html"
    title = "评测模块"
    permission_required = "assessments.view_assessmentmodule"

    def get_queryset(self):
        return visible_assessment_modules_for(self.request.user).select_related("assessment")


class AssessmentModuleDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = AssessmentModule
    template_name = "assessments/module_detail.html"
    context_object_name = "module"
    title = "{name}"
    permission_required = "assessments.view_assessmentmodule"

    def get_queryset(self):
        return visible_assessment_modules_for(self.request.user).prefetch_related(
            "domain_mappings__technical_domain",
            "coach_assignments__user",
            "documents",
            "evidences",
        )


class AssessmentModuleCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = AssessmentModule
    form_class = AssessmentModuleForm
    template_name = "common/form.html"
    title = "新增评测模块"
    permission_required = "assessments.add_assessmentmodule"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(user=self.request.user, permission=self.permission_required)
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if assessment_id := self.request.GET.get("assessment"):
            initial["assessment"] = assessment_id
        return initial

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

    def get_queryset(self):
        return visible_assessment_participants_for(self.request.user).select_related(
            "assessment",
            "role",
            "competition_person",
            "user",
        )


class AssessmentParticipantCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = AssessmentParticipant
    form_class = AssessmentParticipantForm
    template_name = "common/form.html"
    extra_context = {"grid_class": "grid gap-4 md:grid-cols-2"}
    title = "新增参与人员"
    permission_required = "assessments.add_assessmentparticipant"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(user=self.request.user, permission=self.permission_required)
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if assessment_id := self.request.GET.get("assessment"):
            initial["assessment"] = assessment_id
        return initial

    def get_success_url(self):
        return reverse("assessments:participant_detail", args=[self.object.pk])


class AssessmentDocumentCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = AssessmentDocument
    form_class = AssessmentDocumentForm
    template_name = "common/form.html"
    title = "上传评测资料"
    permission_required = "assessments.add_assessmentdocument"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(user=self.request.user, permission=self.permission_required)
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        if assessment_id := self.request.GET.get("assessment"):
            initial["assessment"] = assessment_id
        if module_id := self.request.GET.get("module"):
            initial["module"] = module_id
        return initial

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        form.instance.original_filename = Path(form.cleaned_data["file"].name).name
        return super().form_valid(form)

    def get_success_url(self):
        if self.object.module_id:
            return reverse("assessments:module_detail", args=[self.object.module_id])
        assessment_url = reverse("assessments:assessment_detail", args=[self.object.assessment_id])
        return f"{assessment_url}?tab=modules"


class AssessmentDocumentAccessMixin:
    model = AssessmentDocument

    def get_queryset(self):
        return visible_documents_for(self.request.user).select_related(
            "assessment",
            "module",
            "uploaded_by",
        )


class AssessmentDocumentDetailView(TitleMixin, AssessmentDocumentAccessMixin, DetailView):
    template_name = "common/file_preview_detail.html"
    context_object_name = "document"
    title = "文件预览"
    title_icon = "icon-[tabler--file-search]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = self.object
        if document.module_id:
            source_url = reverse("assessments:module_detail", args=[document.module_id])
            source_label = f"模块：{document.module.name}"
        else:
            assessment_url = reverse("assessments:assessment_detail", args=[document.assessment_id])
            source_url = f"{assessment_url}?tab=modules"
            source_label = f"考核：{document.assessment.name}"

        metadata = [
            FilePreviewMetadata("资料类型", document.get_document_type_display()),
            FilePreviewMetadata("所属考核", document.assessment.name),
            FilePreviewMetadata("所属模块", document.module.name if document.module_id else "公共资料"),
        ]
        if document.version:
            metadata.insert(1, FilePreviewMetadata("版本", document.version))

        context["file_preview"] = build_file_preview_descriptor(
            file=document.file,
            filename=document.filename,
            download_url=reverse("assessments:document_download", args=[document.pk]),
            preview_url=reverse("assessments:document_preview", args=[document.pk]),
            uploader_name=get_user_display_name(document.uploaded_by),
            uploaded_at=document.created_at,
            source_label=source_label,
            source_url=source_url,
            title=document.title,
            description=document.description,
            metadata=tuple(metadata),
        )
        return context


class AssessmentDocumentPreviewView(AssessmentDocumentAccessMixin, DetailView):
    def get(self, request, *args, **kwargs):
        document = self.get_object()
        return build_inline_preview_response(document.file, document.filename)


class AssessmentDocumentDownloadView(AssessmentDocumentAccessMixin, DetailView):

    def get(self, request, *args, **kwargs):
        document = self.get_object()
        return build_download_response(document.file, document.filename)
