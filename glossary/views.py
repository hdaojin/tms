from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, TemplateView, UpdateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin
from standards.models import SkillProject

from .forms import (
    GlossaryEntryForm,
    GlossaryEntryProposalForm,
    GlossaryImportConfirmForm,
    GlossaryImportForm,
    ProfessionalGlossaryForm,
    ProposalRejectForm,
    StatisticsFilterForm,
    StudyAnswerForm,
    StudyStartForm,
)
from .models import GlossaryEntry, GlossaryEntryProposal, GlossaryImport, ProfessionalGlossary, StudyAttempt, StudySession
from .services import (
    approve_proposal,
    confirm_glossary_import,
    create_glossary_import,
    current_or_next_attempt,
    reject_proposal,
    stop_session,
    submit_attempt,
)
from .tables import (
    GlossaryBrowseTable,
    GlossaryEntryTable,
    GlossaryImportTable,
    ProfessionalGlossaryTable,
    ProposalTable,
    StudySessionTable,
)


MANAGE_PERMISSION = "glossary.change_professionalglossary"
ALL_STATS_PERMISSION = "glossary.view_all_study_statistics"


def _session_for_user(request, pk, *, allow_manager=False):
    session = get_object_or_404(StudySession.objects.select_related("user", "glossary", "glossary__skill_project"), pk=pk)
    if session.user_id == request.user.pk:
        return session
    if allow_manager and request.user.has_perm(ALL_STATS_PERMISSION):
        return session
    raise Http404


def _statistics_rows(attempts):
    rows = list(
        attempts.values(
            "entry_id",
            "entry__english_term",
            "entry__acronym",
            "entry__chinese_translation",
            "entry__glossary__name",
            "entry__glossary__skill_project__code",
        )
        .annotate(
            total=Count("id"),
            correct=Count("id", filter=Q(is_correct=True)),
            wrong=Count("id", filter=Q(is_correct=False)),
            en_to_zh_total=Count("id", filter=Q(direction=StudyAttempt.Direction.EN_TO_ZH)),
            en_to_zh_correct=Count(
                "id",
                filter=Q(direction=StudyAttempt.Direction.EN_TO_ZH, is_correct=True),
            ),
            zh_to_en_total=Count("id", filter=Q(direction=StudyAttempt.Direction.ZH_TO_EN)),
            zh_to_en_correct=Count(
                "id",
                filter=Q(direction=StudyAttempt.Direction.ZH_TO_EN, is_correct=True),
            ),
            last_studied=Max("answered_at"),
        )
        .order_by("entry__glossary__skill_project__code", "entry__glossary__name", "entry__english_key")
    )
    for row in rows:
        row["accuracy"] = round(row["correct"] * 100 / row["total"], 1) if row["total"] else 0
        row["en_to_zh_wrong"] = row["en_to_zh_total"] - row["en_to_zh_correct"]
        row["en_to_zh_accuracy"] = (
            round(row["en_to_zh_correct"] * 100 / row["en_to_zh_total"], 1) if row["en_to_zh_total"] else 0
        )
        row["zh_to_en_wrong"] = row["zh_to_en_total"] - row["zh_to_en_correct"]
        row["zh_to_en_accuracy"] = (
            round(row["zh_to_en_correct"] * 100 / row["zh_to_en_total"], 1) if row["zh_to_en_total"] else 0
        )
    return rows


class GlossaryBrowseView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = GlossaryEntry
    table_class = GlossaryBrowseTable
    template_name = "glossary/browse.html"
    paginate_by = 50
    title = "专业词条浏览"
    title_icon = "icon-[tabler--language]"
    permission_required = "glossary.view_glossaryentry"

    def get_queryset(self):
        queryset = GlossaryEntry.objects.filter(is_active=True, glossary__is_active=True).select_related(
            "glossary", "glossary__skill_project"
        )
        query = self.request.GET.get("q", "").strip()
        glossary_id = self.request.GET.get("glossary", "").strip()
        skill_project_id = self.request.GET.get("skill_project", "").strip()
        if query:
            queryset = queryset.filter(
                Q(english_term__icontains=query)
                | Q(acronym__icontains=query)
                | Q(chinese_translation__icontains=query)
            )
        if glossary_id.isdigit():
            queryset = queryset.filter(glossary_id=glossary_id)
        if skill_project_id.isdigit():
            queryset = queryset.filter(glossary__skill_project_id=skill_project_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "query": self.request.GET.get("q", ""),
                "selected_glossary": self.request.GET.get("glossary", ""),
                "selected_skill_project": self.request.GET.get("skill_project", ""),
                "glossaries": ProfessionalGlossary.objects.filter(is_active=True).select_related("skill_project"),
                "skill_projects": SkillProject.objects.filter(is_active=True),
            }
        )
        return context


class ProfessionalGlossaryListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = ProfessionalGlossary
    table_class = ProfessionalGlossaryTable
    template_name = "glossary/table_page.html"
    permission_required = MANAGE_PERMISSION
    title = "专业词库管理"
    title_icon = "icon-[tabler--books]"

    def get_queryset(self):
        return super().get_queryset().select_related("skill_project", "created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("glossary:glossary_create")
        context["create_label"] = "新增专业词库"
        return context


class ProfessionalGlossaryCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ProfessionalGlossary
    form_class = ProfessionalGlossaryForm
    template_name = "common/form.html"
    permission_required = "glossary.add_professionalglossary"
    title = "新增专业词库"
    title_icon = "icon-[tabler--book-2]"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("glossary:glossary_list")


class ProfessionalGlossaryUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = ProfessionalGlossary
    form_class = ProfessionalGlossaryForm
    template_name = "common/form.html"
    permission_required = MANAGE_PERMISSION
    title = "编辑专业词库"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("glossary:glossary_list")


class GlossaryEntryListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = GlossaryEntry
    table_class = GlossaryEntryTable
    template_name = "glossary/table_page.html"
    permission_required = "glossary.view_glossaryentry"
    title = "正式词条"
    title_icon = "icon-[tabler--list-letters]"

    def dispatch(self, request, *args, **kwargs):
        self.glossary = get_object_or_404(ProfessionalGlossary, pk=kwargs["glossary_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return GlossaryEntry.objects.filter(glossary=self.glossary).select_related("glossary", "created_by", "updated_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subtitle"] = str(self.glossary)
        context["create_url"] = f"{reverse('glossary:entry_create')}?glossary={self.glossary.pk}"
        context["create_label"] = "新增正式词条"
        return context


class GlossaryEntryCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = GlossaryEntry
    form_class = GlossaryEntryForm
    template_name = "common/form.html"
    permission_required = "glossary.add_glossaryentry"
    title = "新增正式词条"
    title_icon = "icon-[tabler--plus]"

    def get_initial(self):
        initial = super().get_initial()
        glossary_id = self.request.GET.get("glossary")
        if glossary_id and glossary_id.isdigit():
            initial["glossary"] = int(glossary_id)
        return initial

    def form_valid(self, form):
        form.instance.source = GlossaryEntry.Source.MANAGER
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("glossary:manage_entry_list", args=[self.object.glossary_id])


class GlossaryEntryUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = GlossaryEntry
    form_class = GlossaryEntryForm
    template_name = "common/form.html"
    permission_required = "glossary.change_glossaryentry"
    title = "编辑正式词条"
    title_icon = "icon-[tabler--edit]"

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("glossary:manage_entry_list", args=[self.object.glossary_id])


class ProposalListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = GlossaryEntryProposal
    table_class = ProposalTable
    template_name = "glossary/table_page.html"
    permission_required = "glossary.view_glossaryentryproposal"
    title = "词条提案"
    title_icon = "icon-[tabler--message-plus]"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("glossary", "glossary__skill_project", "submitted_by")
        if self.request.user.has_perm(MANAGE_PERMISSION):
            return queryset
        return queryset.filter(submitted_by=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.has_perm("glossary.add_glossaryentryproposal"):
            context["create_url"] = reverse("glossary:proposal_create")
            context["create_label"] = "提交词条提案"
        return context


class ProposalCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = GlossaryEntryProposal
    form_class = GlossaryEntryProposalForm
    template_name = "common/form.html"
    permission_required = "glossary.add_glossaryentryproposal"
    title = "提交词条提案"
    title_icon = "icon-[tabler--message-plus]"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.submitted_by = self.request.user
        form.instance.status = GlossaryEntryProposal.Status.PENDING
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("glossary:proposal_detail", args=[self.object.pk])


class ProposalScopeMixin:
    def get_queryset(self):
        queryset = GlossaryEntryProposal.objects.select_related(
            "glossary", "glossary__skill_project", "submitted_by", "reviewed_by", "resulting_entry"
        )
        if self.request.user.has_perm(MANAGE_PERMISSION):
            return queryset
        return queryset.filter(submitted_by=self.request.user)


class ProposalDetailView(ProposalScopeMixin, TitleMixin, PermissionRequiredMixin, DetailView):
    model = GlossaryEntryProposal
    template_name = "glossary/proposal_detail.html"
    context_object_name = "proposal"
    permission_required = "glossary.view_glossaryentryproposal"
    title = "词条提案详情"
    title_icon = "icon-[tabler--message-search]"


class ProposalUpdateView(ProposalScopeMixin, TitleMixin, PermissionRequiredMixin, UpdateView):
    model = GlossaryEntryProposal
    form_class = GlossaryEntryProposalForm
    template_name = "common/form.html"
    permission_required = "glossary.change_glossaryentryproposal"
    title = "修改并重新提交"
    title_icon = "icon-[tabler--edit]"

    def get_queryset(self):
        return super().get_queryset().filter(
            submitted_by=self.request.user,
            status__in=[GlossaryEntryProposal.Status.PENDING, GlossaryEntryProposal.Status.REJECTED],
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.status = GlossaryEntryProposal.Status.PENDING
        form.instance.reviewed_by = None
        form.instance.reviewed_at = None
        form.instance.review_note = ""
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("glossary:proposal_detail", args=[self.object.pk])


class ProposalApproveView(PermissionRequiredMixin, View):
    permission_required = MANAGE_PERMISSION

    def post(self, request, *args, **kwargs):
        proposal = get_object_or_404(GlossaryEntryProposal, pk=kwargs["pk"])
        try:
            approve_proposal(proposal, user=request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "词条提案已通过并进入专业词库。")
        return redirect("glossary:proposal_detail", pk=proposal.pk)


class ProposalRejectView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = ProposalRejectForm
    template_name = "common/form.html"
    permission_required = MANAGE_PERMISSION
    title = "驳回词条提案"
    title_icon = "icon-[tabler--x]"

    def dispatch(self, request, *args, **kwargs):
        self.proposal = get_object_or_404(GlossaryEntryProposal, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            reject_proposal(self.proposal, user=self.request.user, note=form.cleaned_data["review_note"])
        except ValidationError as exc:
            form.add_error("review_note", "; ".join(exc.messages))
            return self.form_invalid(form)
        messages.success(self.request, "词条提案已驳回。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("glossary:proposal_detail", args=[self.proposal.pk])


class GlossaryImportListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = GlossaryImport
    table_class = GlossaryImportTable
    template_name = "glossary/table_page.html"
    permission_required = "glossary.view_glossaryimport"
    title = "词库导入记录"
    title_icon = "icon-[tabler--file-spreadsheet]"

    def get_queryset(self):
        return super().get_queryset().select_related("glossary", "glossary__skill_project", "imported_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("glossary:import_create")
        context["create_label"] = "导入 Smartcat XLSX"
        return context


class GlossaryImportCreateView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = GlossaryImportForm
    template_name = "glossary/import_form.html"
    permission_required = "glossary.add_glossaryimport"
    title = "导入 Smartcat XLSX"
    title_icon = "icon-[tabler--upload]"

    def form_valid(self, form):
        self.object = create_glossary_import(
            form.cleaned_data["glossary"],
            form.cleaned_data["file"],
            user=self.request.user,
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("glossary:import_preview", args=[self.object.pk])


class GlossaryImportPreviewView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = GlossaryImport
    template_name = "glossary/import_preview.html"
    context_object_name = "glossary_import"
    permission_required = "glossary.change_glossaryimport"
    title = "确认词库导入"
    title_icon = "icon-[tabler--file-check]"

    def get_queryset(self):
        return super().get_queryset().select_related("glossary", "glossary__skill_project", "imported_by")

    def get_form(self):
        return GlossaryImportConfirmForm(self.request.POST or None, payload=self.object.parsed_payload)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        try:
            confirmed = confirm_glossary_import(self.object, form.decisions(), user=request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            self.object.refresh_from_db()
            return self.render_to_response(self.get_context_data(form=form))
        messages.success(
            request,
            f"导入完成：新增 {confirmed.result_summary['created']}，覆盖 "
            f"{confirmed.result_summary['overwritten']}，跳过 {confirmed.result_summary['skipped']}。",
        )
        return redirect("glossary:import_detail", pk=confirmed.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", self.get_form())
        return context


class GlossaryImportDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    model = GlossaryImport
    template_name = "glossary/import_detail.html"
    context_object_name = "glossary_import"
    permission_required = "glossary.view_glossaryimport"
    title = "词库导入详情"
    title_icon = "icon-[tabler--file-description]"

    def get_queryset(self):
        return super().get_queryset().select_related("glossary", "glossary__skill_project", "imported_by")


class GlossaryImportDownloadView(PermissionRequiredMixin, View):
    permission_required = "glossary.view_glossaryimport"

    def get(self, request, *args, **kwargs):
        glossary_import = get_object_or_404(GlossaryImport, pk=kwargs["pk"])
        if not glossary_import.source_file:
            raise Http404
        return FileResponse(
            glossary_import.source_file.open("rb"),
            as_attachment=True,
            filename=glossary_import.original_filename,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class StudyStartView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = StudyStartForm
    template_name = "glossary/study_start.html"
    title = "开始词汇学习"
    title_icon = "icon-[tabler--brain]"
    permission_required = ("glossary.view_glossaryentry", "glossary.add_studysession")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_session"] = StudySession.objects.filter(
            user=self.request.user,
            status=StudySession.Status.ACTIVE,
        ).select_related("glossary", "glossary__skill_project").first()
        return context

    def form_valid(self, form):
        active = StudySession.objects.filter(user=self.request.user, status=StudySession.Status.ACTIVE).first()
        if active:
            return redirect("glossary:study_session", pk=active.pk)
        self.object = StudySession.objects.create(
            user=self.request.user,
            glossary=form.cleaned_data["glossary"],
            mode=form.cleaned_data["mode"],
            target_count=form.cleaned_data["target_count"],
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("glossary:study_session", args=[self.object.pk])


class StudySessionView(TitleMixin, PermissionRequiredMixin, View):
    title = "专业词汇学习"
    title_icon = "icon-[tabler--brain]"
    permission_required = "glossary.view_studysession"

    def get(self, request, *args, **kwargs):
        session = _session_for_user(request, kwargs["pk"])
        if session.status != StudySession.Status.ACTIVE:
            return redirect("glossary:session_summary", pk=session.pk)
        try:
            attempt = current_or_next_attempt(session)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            stop_session(session)
            return redirect("glossary:session_summary", pk=session.pk)
        if attempt is None:
            return redirect("glossary:session_summary", pk=session.pk)
        return render(
            request,
            "glossary/study.html",
            {
                "title": self.title,
                "title_icon": self.title_icon,
                "session": session,
                "attempt": attempt,
                "form": StudyAnswerForm(),
                "feedback": False,
            },
        )


class StudyAnswerView(PermissionRequiredMixin, View):
    permission_required = ("glossary.change_studysession", "glossary.add_studyattempt")

    def post(self, request, *args, **kwargs):
        session = _session_for_user(request, kwargs["pk"])
        attempt = get_object_or_404(StudyAttempt, pk=request.POST.get("attempt_id"), session=session)
        form = StudyAnswerForm(request.POST)
        answer = ""
        if request.POST.get("unknown") == "1":
            answer = ""
        elif form.is_valid():
            answer = form.cleaned_data["answer"]
        else:
            template = "glossary/study_panel.html" if request.htmx else "glossary/study.html"
            return render(
                request,
                template,
                {
                    "title": "专业词汇学习",
                    "title_icon": "icon-[tabler--brain]",
                    "session": session,
                    "attempt": attempt,
                    "form": form,
                    "feedback": False,
                },
            )
        try:
            attempt = submit_attempt(attempt, answer)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect("glossary:study_session", pk=session.pk)
        template = "glossary/study_panel.html" if request.htmx else "glossary/study.html"
        return render(
            request,
            template,
            {
                "title": "专业词汇学习",
                "title_icon": "icon-[tabler--brain]",
                "session": session,
                "attempt": attempt,
                "feedback": True,
            },
        )


class StudyStopView(PermissionRequiredMixin, View):
    permission_required = "glossary.change_studysession"

    def post(self, request, *args, **kwargs):
        session = _session_for_user(request, kwargs["pk"])
        stop_session(session)
        messages.info(request, "学习会话已停止。")
        return redirect("glossary:session_summary", pk=session.pk)


class StudySessionSummaryView(TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "glossary/study_summary.html"
    title = "学习会话总结"
    title_icon = "icon-[tabler--chart-dots]"
    permission_required = "glossary.view_studysession"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = _session_for_user(self.request, self.kwargs["pk"], allow_manager=True)
        attempts = list(session.attempts.filter(answered_at__isnull=False).select_related("entry").order_by("sequence"))
        correct = sum(1 for attempt in attempts if attempt.is_correct)
        duration_seconds = max(int(((session.ended_at or timezone.now()) - session.started_at).total_seconds()), 0)
        context.update(
            {
                "session": session,
                "attempts": attempts,
                "correct": correct,
                "wrong": len(attempts) - correct,
                "accuracy": round(correct * 100 / len(attempts), 1) if attempts else 0,
                "duration_text": f"{duration_seconds // 60} 分 {duration_seconds % 60} 秒",
            }
        )
        return context


class BaseStatisticsView(TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "glossary/statistics.html"
    include_user_filter = False
    permission_required = "glossary.view_studysession"

    def get_target_user(self, form):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = StatisticsFilterForm(self.request.GET or None, include_user=self.include_user_filter)
        form.is_valid()
        target_user = self.get_target_user(form)
        attempts = StudyAttempt.objects.filter(answered_at__isnull=False).select_related(
            "entry", "entry__glossary", "session", "session__user"
        )
        sessions = StudySession.objects.select_related("user", "glossary", "glossary__skill_project")
        if target_user:
            attempts = attempts.filter(session__user=target_user)
            sessions = sessions.filter(user=target_user)
        if form.is_valid():
            project = form.cleaned_data.get("skill_project")
            glossary = form.cleaned_data.get("glossary")
            date_from = form.cleaned_data.get("date_from")
            date_to = form.cleaned_data.get("date_to")
            if project:
                attempts = attempts.filter(entry__glossary__skill_project=project)
                sessions = sessions.filter(glossary__skill_project=project)
            if glossary:
                attempts = attempts.filter(entry__glossary=glossary)
                sessions = sessions.filter(glossary=glossary)
            if date_from:
                attempts = attempts.filter(answered_at__date__gte=date_from)
                sessions = sessions.filter(started_at__date__gte=date_from)
            if date_to:
                attempts = attempts.filter(answered_at__date__lte=date_to)
                sessions = sessions.filter(started_at__date__lte=date_to)
        total = attempts.count()
        correct = attempts.filter(is_correct=True).count()
        context.update(
            {
                "filter_form": form,
                "target_user": target_user,
                "session_table": StudySessionTable(list(sessions.order_by("-started_at")[:100])),
                "entry_rows": _statistics_rows(attempts),
                "total": total,
                "correct": correct,
                "wrong": total - correct,
                "accuracy": round(correct * 100 / total, 1) if total else 0,
            }
        )
        return context


class MyStatisticsView(BaseStatisticsView):
    title = "我的词汇学习统计"
    title_icon = "icon-[tabler--chart-bar]"


class AllStatisticsView(BaseStatisticsView):
    permission_required = ALL_STATS_PERMISSION
    include_user_filter = True
    title = "全部词汇学习统计"
    title_icon = "icon-[tabler--chart-histogram]"

    def get_target_user(self, form):
        return form.cleaned_data.get("user") if form.is_valid() else None
