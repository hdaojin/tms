from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, FormView, TemplateView, View
from django_tables2 import SingleTableView

from assessments.models import AssessmentModule, AssessmentParticipant, CompetitionRole
from assessments.tables import AssessmentParticipantTable
from core.utils.mixins import TitleMixin

from .forms import OnlineScoringForm, ScoringImportForm, ScoringResultForm
from .models import ScoringAspect, ScoringResult, ScoringScheme, ScoringSchemeImport
from .parser import WorkbookParseError
from .registry import PARSER_DEFINITIONS
from .services import (
    confirm_scheme_import,
    enabled_parser_configs,
    parse_scheme_document,
    record_scoring_result,
    scheme_import_consistency_report,
)
from .selectors import (
    module_scoring_summary,
    scoring_modules_in_scope_for,
    scoring_scheme_imports_in_scope_for,
    scoring_schemes_in_scope_for,
)
from .tables import ScoringAspectTable, ScoringSchemeTable


ONLINE_SCORING_PERMISSIONS = (
    "scoring.view_scoringscheme",
    "scoring.view_scoringresult",
    "scoring.view_all_scoringresult",
)


def _online_scoring_module(user, module_pk):
    scheme_module_ids = scoring_schemes_in_scope_for(user).values("assessment_module_id")
    queryset = scoring_modules_in_scope_for(user, "scoring.view_scoringresult").filter(
        pk=module_pk,
        pk__in=scheme_module_ids,
    )
    return get_object_or_404(queryset.select_related("assessment", "assessment__skill_project"))


def _add_validation_errors(form, exc):
    if hasattr(exc, "message_dict"):
        for field, errors in exc.message_dict.items():
            form.add_error(field if field in form.fields else None, errors)
        return
    form.add_error(None, exc.messages)


def _online_scoring_context(
    user,
    module,
    *,
    perspective="participant",
    participant_id=None,
    aspect_id=None,
    bound_form=None,
    bound_key=None,
    saved_key=None,
):
    scheme = get_object_or_404(scoring_schemes_in_scope_for(user), assessment_module=module)
    participants = list(
        module.assessment.participants.filter(role__category=CompetitionRole.Category.COMPETITOR)
        .select_related("role", "user", "competition_person")
        .order_by("role__order", "display_name", "pk")
    )
    aspects = list(scheme.aspects.select_related("subcriterion").order_by("subcriterion__order", "order", "pk"))
    perspective = perspective if perspective in {"participant", "aspect"} else "participant"
    selected_participant = None
    selected_aspect = None
    try:
        participant_pk = int(participant_id) if participant_id else None
        aspect_pk = int(aspect_id) if aspect_id else None
    except (TypeError, ValueError) as exc:
        raise Http404("评分工作台筛选参数无效。") from exc
    if participants:
        selected_participant = participants[0]
        if participant_pk:
            selected_participant = next((item for item in participants if item.pk == participant_pk), None)
            if selected_participant is None:
                raise Http404("未找到当前评测中的选手。")
    if aspects:
        selected_aspect = aspects[0]
        if aspect_pk:
            selected_aspect = next((item for item in aspects if item.pk == aspect_pk), None)
            if selected_aspect is None:
                raise Http404("未找到当前模块中的评分点。")

    results = {
        (result.participant_id, result.aspect_id): result
        for result in ScoringResult.objects.filter(
            participant_id__in=[item.pk for item in participants],
            aspect_id__in=[item.pk for item in aspects],
        ).select_related("entered_by", "updated_by", "confirmed_by")
    }
    module_queryset = AssessmentModule.objects.filter(pk=module.pk)
    can_add = scoring_modules_in_scope_for(user, "scoring.add_scoringresult", module_queryset).exists()
    can_change = scoring_modules_in_scope_for(user, "scoring.change_scoringresult", module_queryset).exists()
    row_pairs = []
    if perspective == "participant" and selected_participant:
        row_pairs = [(selected_participant, aspect) for aspect in aspects]
    elif perspective == "aspect" and selected_aspect:
        row_pairs = [(participant, selected_aspect) for participant in participants]
    scoring_rows = []
    for participant, aspect in row_pairs:
        key = (participant.pk, aspect.pk)
        result = results.get(key)
        form = bound_form if bound_key == key else OnlineScoringForm(aspect=aspect, result=result)
        scoring_rows.append(
            {
                "participant": participant,
                "aspect": aspect,
                "result": result,
                "form": form,
                "can_edit": can_change if result else can_add,
                "saved": saved_key == key,
            }
        )
    return {
        "module": module,
        "scheme": scheme,
        "participants": participants,
        "aspects": aspects,
        "perspective": perspective,
        "selected_participant": selected_participant,
        "selected_aspect": selected_aspect,
        "scoring_rows": scoring_rows,
        "summary": module_scoring_summary(module, scheme),
    }


class ScoringSchemeListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = ScoringScheme
    table_class = ScoringSchemeTable
    template_name = "scoring/scheme_list.html"
    title = "评分方案"
    title_icon = "icon-[tabler--clipboard-check]"
    permission_required = "scoring.view_scoringscheme"

    def get_queryset(self):
        return scoring_schemes_in_scope_for(self.request.user).select_related(
            "assessment_module",
            "assessment_module__assessment",
        )


class ScoringSchemeDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = ScoringScheme
    template_name = "scoring/scheme_detail.html"
    context_object_name = "scheme"
    title = "{title}"
    title_icon = "icon-[tabler--clipboard-check]"
    permission_required = "scoring.view_scoringscheme"

    def get_queryset(self):
        return scoring_schemes_in_scope_for(self.request.user).select_related(
            "assessment_module",
            "assessment_module__assessment",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        aspect_table = ScoringAspectTable(self.object.aspects.select_related("subcriterion"))
        participants = AssessmentParticipant.objects.none()
        if self.request.user.has_perm("scoring.view_scoringresult"):
            participant_scope = self.object.assessment_module.assessment.participants.filter(
                role__category=CompetitionRole.Category.COMPETITOR,
            )
            can_view_all = (
                self.request.user.has_perm("scoring.view_all_scoringresult")
                and scoring_modules_in_scope_for(
                    self.request.user,
                    "scoring.view_scoringresult",
                    AssessmentModule.objects.filter(pk=self.object.assessment_module_id),
                ).exists()
            )
            if can_view_all:
                participants = participant_scope.select_related("assessment", "role")
            else:
                participants = participant_scope.filter(user=self.request.user).select_related("assessment", "role")
        participant_table = AssessmentParticipantTable(participants)
        context["aspect_table"] = aspect_table
        context["participant_table"] = participant_table
        context["can_score_online"] = (
            self.request.user.has_perms(ONLINE_SCORING_PERMISSIONS)
            and scoring_modules_in_scope_for(
                self.request.user,
                "scoring.view_scoringresult",
                AssessmentModule.objects.filter(pk=self.object.assessment_module_id),
            ).exists()
        )
        return context


class ScoringImportView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = ScoringImportForm
    template_name = "scoring/scheme_import_form.html"
    permission_required = "scoring.add_scoringscheme"
    title = "导入评分表"
    title_icon = "icon-[tabler--upload]"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            user=self.request.user,
            permission=self.permission_required,
            module_id=self.request.GET.get("module"),
        )
        return kwargs

    def form_valid(self, form):
        try:
            self.object = parse_scheme_document(
                form.cleaned_data["source_document"],
                form.cleaned_data["parser_config"],
                user=self.request.user,
            )
        except WorkbookParseError as exc:
            for error in exc.errors:
                form.add_error("source_document", error)
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["parser_configs"] = enabled_parser_configs()
        return context

    def get_success_url(self):
        return reverse("scoring:scheme_import_preview", args=[self.object.pk])


class ScoringSchemeImportPreviewView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = ScoringSchemeImport
    template_name = "scoring/scheme_import_preview.html"
    context_object_name = "scheme_import"
    permission_required = "scoring.add_scoringscheme"
    title = "确认评分表导入"
    title_icon = "icon-[tabler--clipboard-check]"

    def get_queryset(self):
        return scoring_scheme_imports_in_scope_for(self.request.user).select_related(
            "assessment_module",
            "assessment_module__assessment",
            "source_document",
            "scheme",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["consistency_report"] = scheme_import_consistency_report(self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            scheme = confirm_scheme_import(self.object, user=request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return self.get(request, *args, **kwargs)
        messages.success(request, "评分方案已生成。")
        return self.redirect_to_scheme(scheme)

    def redirect_to_scheme(self, scheme):
        from django.shortcuts import redirect

        return redirect("scoring:scheme_detail", pk=scheme.pk)


class ScoringParserTemplateDownloadView(PermissionRequiredMixin, View):
    permission_required = "scoring.add_scoringscheme"

    def get(self, request, *args, **kwargs):
        parser_key = kwargs["parser_key"]
        definition = PARSER_DEFINITIONS.get(parser_key)
        if not definition or not definition.template_path.exists():
            raise Http404("未找到解析器模板。")
        return FileResponse(
            definition.template_path.open("rb"),
            as_attachment=True,
            filename=definition.template_filename,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class OnlineScoringWorkspaceView(TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "scoring/online_scoring.html"
    permission_required = ONLINE_SCORING_PERMISSIONS
    title = "在线评分"
    title_icon = "icon-[tabler--scoreboard]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        module = _online_scoring_module(self.request.user, self.kwargs["module_pk"])
        context.update(
            _online_scoring_context(
                self.request.user,
                module,
                perspective=self.request.GET.get("perspective", "participant"),
                participant_id=self.request.GET.get("participant"),
                aspect_id=self.request.GET.get("aspect"),
            )
        )
        return context

    def get_template_names(self):
        if self.request.htmx:
            return [f"{self.template_name}#workspace"]
        return [self.template_name]


class OnlineScoringEntryView(PermissionRequiredMixin, View):
    permission_required = ONLINE_SCORING_PERMISSIONS

    def post(self, request, *args, **kwargs):
        module = _online_scoring_module(request.user, kwargs["module_pk"])
        participant = get_object_or_404(
            module.assessment.participants.select_related("role"),
            pk=kwargs["participant_pk"],
            role__category=CompetitionRole.Category.COMPETITOR,
        )
        aspect = get_object_or_404(
            ScoringAspect.objects.select_related("scheme__assessment_module"),
            pk=kwargs["aspect_pk"],
            scheme__assessment_module=module,
        )
        existing = ScoringResult.objects.filter(participant=participant, aspect=aspect).first()
        form = OnlineScoringForm(request.POST, aspect=aspect, result=existing)
        saved = False
        if form.is_valid():
            try:
                record_scoring_result(
                    participant=participant,
                    aspect=aspect,
                    score_awarded=form.cleaned_data["score_awarded"],
                    user=request.user,
                    source=ScoringResult.Source.ONLINE,
                    evidence=form.cleaned_data["evidence"],
                    confirm=form.cleaned_data["confirm"],
                    reason=form.cleaned_data["reason"],
                )
            except ValidationError as exc:
                _add_validation_errors(form, exc)
            else:
                saved = True

        perspective = request.POST.get("perspective", "participant")
        participant_id = participant.pk if perspective == "participant" else None
        aspect_id = aspect.pk if perspective == "aspect" else None
        key = (participant.pk, aspect.pk)
        if saved and not request.htmx:
            messages.success(request, "评分已保存。")
            query = f"perspective={perspective}"
            query += f"&participant={participant.pk}" if perspective == "participant" else f"&aspect={aspect.pk}"
            return HttpResponseRedirect(f"{reverse('scoring:online_scoring', args=[module.pk])}?{query}")
        context = _online_scoring_context(
            request.user,
            module,
            perspective=perspective,
            participant_id=participant_id,
            aspect_id=aspect_id,
            bound_form=None if saved else form,
            bound_key=None if saved else key,
            saved_key=key if saved else None,
        )
        template_name = (
            "scoring/online_scoring.html#workspace" if request.htmx else "scoring/online_scoring.html"
        )
        return render(request, template_name, context)


class ScoringResultCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ScoringResult
    form_class = ScoringResultForm
    template_name = "common/form.html"
    permission_required = "scoring.add_scoringresult"
    title = "录入评分结果"
    title_icon = "icon-[tabler--plus]"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(user=self.request.user, permission=self.permission_required)
        return kwargs

    def form_valid(self, form):
        try:
            self.object = record_scoring_result(
                participant=form.cleaned_data["participant"],
                aspect=form.cleaned_data["aspect"],
                score_awarded=form.cleaned_data["score_awarded"],
                user=self.request.user,
                source=ScoringResult.Source.MANUAL,
                evidence=form.cleaned_data["evidence"],
            )
        except ValidationError as exc:
            _add_validation_errors(form, exc)
            return self.form_invalid(form)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("assessments:participant_detail", args=[self.object.participant_id])
