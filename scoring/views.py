from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, FormView, UpdateView, View
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .forms import ScoringImportForm, ScoringParticipantForm, ScoringResultForm
from .models import ScoringParticipant, ScoringResult, ScoringScheme, ScoringSchemeImport
from .parser import WorkbookParseError
from .registry import PARSER_DEFINITIONS
from .services import confirm_scheme_import, enabled_parser_configs, parse_scheme_upload
from .selectors import scoring_participants_visible_to
from .tables import ScoringAspectTable, ScoringParticipantTable, ScoringSchemeTable


class ScoringSchemeListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = ScoringScheme
    table_class = ScoringSchemeTable
    template_name = "scoring/scheme_list.html"
    title = "评分方案"
    title_icon = "icon-[tabler--clipboard-check]"
    permission_required = "scoring.view_scoringscheme"

    def get_queryset(self):
        return super().get_queryset().select_related("event_module", "event_module__event")


class ScoringSchemeDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = ScoringScheme
    template_name = "scoring/scheme_detail.html"
    context_object_name = "scheme"
    title = "{title}"
    title_icon = "icon-[tabler--clipboard-check]"
    permission_required = "scoring.view_scoringscheme"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        aspect_table = ScoringAspectTable(self.object.aspects.select_related("subcriterion"))
        participants = ScoringParticipant.objects.none()
        if self.request.user.has_perm("scoring.view_scoringparticipant"):
            participants = scoring_participants_visible_to(
                self.request.user, self.object.participants.all()
            )
        participant_table = ScoringParticipantTable(participants)
        context["aspect_table"] = aspect_table
        context["participant_table"] = participant_table
        return context


class ScoringImportView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = ScoringImportForm
    template_name = "scoring/scheme_import_form.html"
    permission_required = "scoring.add_scoringscheme"
    title = "导入评分表"
    title_icon = "icon-[tabler--upload]"

    def form_valid(self, form):
        try:
            self.object = parse_scheme_upload(
                form.cleaned_data["event_module"],
                form.cleaned_data["file"],
                form.cleaned_data["parser_config"],
                user=self.request.user,
            )
        except WorkbookParseError as exc:
            for error in exc.errors:
                form.add_error("file", error)
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
        return super().get_queryset().select_related("event_module", "event_module__event", "source_asset", "scheme")

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


class ScoringParticipantCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ScoringParticipant
    form_class = ScoringParticipantForm
    template_name = "common/form.html"
    permission_required = "scoring.add_scoringparticipant"
    title = "新增参评对象"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("scoring:scheme_detail", args=[self.object.scheme_id])


class ScoringParticipantDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = ScoringParticipant
    template_name = "scoring/participant_detail.html"
    context_object_name = "participant"
    title = "{display_name}"
    title_icon = "icon-[tabler--user-check]"
    permission_required = "scoring.view_scoringparticipant"

    def get_queryset(self):
        return scoring_participants_visible_to(self.request.user, super().get_queryset())


class ScoringParticipantUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = ScoringParticipant
    form_class = ScoringParticipantForm
    template_name = "common/form.html"
    permission_required = "scoring.change_scoringparticipant"
    title = "编辑参评对象"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("scoring:participant_detail", args=[self.object.pk])


class ScoringResultCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ScoringResult
    form_class = ScoringResultForm
    template_name = "common/form.html"
    permission_required = "scoring.add_scoringresult"
    title = "录入评分结果"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("scoring:participant_detail", args=[self.object.participant_id])

