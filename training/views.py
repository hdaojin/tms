from calendar import monthrange
from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView
from django_tables2 import SingleTableView

from core.permissions.roles import ROLE_COACH, ROLE_COMPETITOR
from core.utils.mixins import TitleMixin

from .forms import TrainingCycleForm, TrainingLogForm, TrainingLogUpdateForm
from .models import TrainingCycle, TrainingLog
from .services import build_training_log_archive, create_training_log_asset
from .tables import TrainingCycleTable, TrainingLogTable


class MonthFilterMixin:
    month_option_count = 12

    def _get_selected_year_month(self):
        today = timezone.localdate()
        try:
            year = int(self.request.GET.get("year") or today.year)
        except (TypeError, ValueError):
            year = today.year
        try:
            month = int(self.request.GET.get("month") or today.month)
        except (TypeError, ValueError):
            month = today.month
        if month < 1 or month > 12:
            month = today.month
        return year, month

    def _get_selected_month_range(self):
        year, month = self._get_selected_year_month()
        return date(year, month, 1), date(year, month, monthrange(year, month)[1])

    def _get_recent_months(self):
        today = timezone.localdate()
        year, month = today.year, today.month
        months = []
        for _ in range(self.month_option_count):
            months.append({"year": year, "month": month, "name": f"{year}年{month:02d}月"})
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return months

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month = self._get_selected_year_month()
        context.update({"months": self._get_recent_months(), "selected_year": year, "selected_month": month})
        return context


class TrainingCycleListView(TitleMixin, LoginRequiredMixin, SingleTableView):
    model = TrainingCycle
    table_class = TrainingCycleTable
    template_name = "training/cycle_list.html"
    title = "训练周期"
    title_icon = "icon-[tabler--calendar-time]"


class TrainingCycleDetailView(TitleMixin, LoginRequiredMixin, DetailView):
    model = TrainingCycle
    template_name = "training/cycle_detail.html"
    context_object_name = "cycle"
    title = "{name}"
    title_icon = "icon-[tabler--calendar-time]"


class TrainingCycleCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingCycle
    form_class = TrainingCycleForm
    template_name = "common/form.html"
    permission_required = "training.add_trainingcycle"
    title = "新增训练周期"
    title_icon = "icon-[tabler--plus]"

    def get_success_url(self):
        return reverse("training:cycle_detail", args=[self.object.pk])


class TrainingCycleUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = TrainingCycle
    form_class = TrainingCycleForm
    template_name = "common/form.html"
    permission_required = "training.change_trainingcycle"
    title = "编辑训练周期"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("training:cycle_detail", args=[self.object.pk])


class TrainingLogListView(MonthFilterMixin, TitleMixin, LoginRequiredMixin, SingleTableView):
    model = TrainingLog
    table_class = TrainingLogTable
    template_name = "training/log_list.html"
    title = "训练日志"
    title_icon = "icon-[tabler--file-text]"

    def get_queryset(self):
        start, end = self._get_selected_month_range()
        qs = super().get_queryset().select_related("training_cycle", "capability_domain", "uploaded_by")
        if self.request.user.has_perm("training.view_all_traininglog"):
            return qs.filter(training_date__range=(start, end))
        return qs.filter(uploaded_by=self.request.user, training_date__range=(start, end))


class TrainingLogDetailView(TitleMixin, LoginRequiredMixin, DetailView):
    model = TrainingLog
    template_name = "training/log_detail.html"
    context_object_name = "log"
    title = "{topic}"
    title_icon = "icon-[tabler--file-text]"


class TrainingLogCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingLog
    form_class = TrainingLogForm
    template_name = "common/form.html"
    permission_required = "training.add_traininglog"
    title = "上传训练日志"
    title_icon = "icon-[tabler--upload]"

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        response = super().form_valid(form)
        create_training_log_asset(self.object, form.cleaned_data["file"], user=self.request.user)
        return response

    def get_success_url(self):
        return reverse("training:log_detail", args=[self.object.pk])


class TrainingLogUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = TrainingLog
    form_class = TrainingLogUpdateForm
    template_name = "common/form.html"
    permission_required = "training.change_traininglog"
    title = "编辑训练日志"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("training:log_detail", args=[self.object.pk])


class TrainingLogMonthlyStatView(MonthFilterMixin, TitleMixin, LoginRequiredMixin, TemplateView):
    template_name = "training/monthly_stats.html"
    title = "训练日志提交统计"
    title_icon = "icon-[tabler--chart-bar]"

    def _get_add_perm_users(self, role_codename):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return (
            User.objects.filter(is_active=True, groups__profile__codename=role_codename)
            .filter(
                Q(user_permissions__codename="add_traininglog", user_permissions__content_type__app_label="training")
                | Q(groups__permissions__codename="add_traininglog", groups__permissions__content_type__app_label="training")
            )
            .distinct()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start, end = self._get_selected_month_range()
        today = timezone.localdate()
        if start.year == today.year and start.month == today.month:
            end = min(end, today)
        comp_qs = self._get_add_perm_users(ROLE_COMPETITOR)
        coach_qs = self._get_add_perm_users(ROLE_COACH)
        comp_names = {u.id: u.display_name for u in comp_qs}
        coach_names = {u.id: u.display_name for u in coach_qs}
        user_ids = set(comp_names) | set(coach_names)
        rows = TrainingLog.objects.filter(training_date__range=(start, end), uploaded_by_id__in=user_ids).values_list(
            "training_date", "uploaded_by_id"
        )
        by_day = {}
        for day, user_id in rows:
            by_day.setdefault(day, set()).add(user_id)
        data = []
        cur = start
        while cur <= end:
            submitted = by_day.get(cur, set())
            data.append(
                {
                    "date": cur,
                    "submitted_competitors": " ".join(sorted(comp_names[uid] for uid in submitted if uid in comp_names)) or "无",
                    "unsubmitted_competitors": " ".join(sorted(name for uid, name in comp_names.items() if uid not in submitted)) or "全部提交",
                    "submitted_coaches": " ".join(sorted(coach_names[uid] for uid in submitted if uid in coach_names)) or "无",
                }
            )
            cur += timedelta(days=1)
        context["rows"] = data
        return context


class TrainingLogArchiveExportView(MonthFilterMixin, LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    raise_exception = True

    def test_func(self):
        return self.request.user.has_perm("training.export_traininglog_archive")

    def get(self, request, *args, **kwargs):
        start, end = self._get_selected_month_range()
        qs = TrainingLog.objects.filter(training_date__range=(start, end))
        cycle_id = request.GET.get("cycle")
        if cycle_id:
            qs = qs.filter(training_cycle_id=cycle_id)
        data = build_training_log_archive(qs)
        filename = f"training-logs-{start:%Y-%m}.zip"
        response = HttpResponse(data, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

# Create your views here.
