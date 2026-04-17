# traininglogs/views.py
from calendar import monthrange
from datetime import date, timedelta

from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
)
from django.views.generic import CreateView, DetailView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django_tables2 import SingleTableView

from core.constants import GROUP_COACH, GROUP_COMPETITOR
from core.utils.mixins import TitleMixin, CrossGroupAccessMixin, OwnerRequiredMixin
from core.utils.pdf_response import create_pdf_preview_view

from .models import TrainingLog
from .forms import TrainingLogCreateForm
from .tables import TrainingLogTable, TrainingLogOthersTable, MonthlyStatTable


pagination_per_page = 18


class TraininglogMonthFilterMixin:
    month_option_count = 12

    def _get_selected_year_month(self):
        today = timezone.localdate()
        try:
            year = int(self.request.GET.get('year') or today.year)
        except (TypeError, ValueError):
            year = today.year
        try:
            month = int(self.request.GET.get('month') or today.month)
        except (TypeError, ValueError):
            month = today.month
        if month < 1 or month > 12:
            month = today.month
        return year, month

    def _get_selected_month_range(self):
        year, month = self._get_selected_year_month()
        days_in_month = monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, days_in_month)

    def _get_recent_months(self):
        today = timezone.localdate()
        year, month = today.year, today.month
        months = []
        for _ in range(self.month_option_count):
            months.append({'year': year, 'month': month, 'name': f"{year}年{month:02d}月"})
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return months

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month = self._get_selected_year_month()
        context.update({
            'months': self._get_recent_months(),
            'selected_year': year,
            'selected_month': month,
        })
        return context


# 训练日志上传视图
class TrainingLogUploadView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = TrainingLog
    form_class = TrainingLogCreateForm
    template_name = "traininglogs/traininglog_upload.html"
    success_url = reverse_lazy("traininglogs:traininglog_list")
    permission_required = "traininglogs.add_traininglog"
    raise_exception = True
    title = "上传训练日志"
    title_icon = "icon-[tabler--upload]"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, "训练日志上传成功！")
        return super().form_valid(form)


# 训练日志列表视图
class TraininglogListView(
    TraininglogMonthFilterMixin,
    TitleMixin,
    LoginRequiredMixin,
    SingleTableView,
):
    model = TrainingLog
    table_class = TrainingLogTable
    template_name = "traininglogs/traininglog_list.html"
    paginate_by = pagination_per_page
    title = "我的训练日志"
    title_icon = "icon-[tabler--file-stack]"

    def get_queryset(self):
        qs = super().get_queryset().select_related('uploaded_by', 'module')
        if self.request.user.is_authenticated:
            start, end = self._get_selected_month_range()
            return qs.filter(
                uploaded_by=self.request.user,
                training_date__range=(start, end),
            )
        return qs.none()


def _check_traininglog_cross_group_access(request, obj):
    """检查训练日志的跨组访问权限"""
    user = request.user
    if not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    if getattr(obj, "uploaded_by_id", None) == getattr(user, "pk", None):
        return True
    
    owner_user = getattr(obj, "uploaded_by", None)
    owner_groups = (
        set(owner_user.groups.values_list("name", flat=True))
        if owner_user is not None
        else set()
    )
    user_groups = (
        set(user.groups.values_list("name", flat=True))
        if getattr(user, "pk", None)
        else set()
    )
    return (GROUP_COMPETITOR in user_groups and GROUP_COACH in owner_groups) or (
        GROUP_COACH in user_groups and GROUP_COMPETITOR in owner_groups
    )


# 使用工厂函数创建 PDF 预览视图
traininglog_pdf_inline = create_pdf_preview_view(
    TrainingLog,
    permission_checker=_check_traininglog_cross_group_access
)


class TrainingLogDetailView(TitleMixin, CrossGroupAccessMixin, LoginRequiredMixin, DetailView):
    model = TrainingLog
    template_name = "traininglogs/traininglog_detail.html"
    context_object_name = "traininglog"
    owner_field = "uploaded_by"
    title = "{uploaded_by}的{training_date}训练日志"
    title_icon = "icon-[tabler--file-text]"

    def get_queryset(self):
        return super().get_queryset().select_related('uploaded_by', 'module')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pdf_preview_url"] = reverse(
            "traininglogs:traininglog_pdf_inline", args=[self.object.pk]  # type: ignore
        )
        return context


class TrainingLogDeleteView(OwnerRequiredMixin, LoginRequiredMixin, DeleteView):
    model = TrainingLog
    success_url = reverse_lazy("traininglogs:traininglog_list")
    raise_exception = True
    owner_field = "uploaded_by"


class CoachTraininglogListView(
    TraininglogMonthFilterMixin,
    TitleMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    SingleTableView,
):
    """教练训练日志：展示所有“教练”上传的日志。"""

    model = TrainingLog
    table_class = TrainingLogOthersTable
    template_name = "traininglogs/traininglog_list.html"
    permission_required = "traininglogs.view_coach_traininglog"
    raise_exception = True
    paginate_by = pagination_per_page
    title = "教练训练日志"
    title_icon = "icon-[tabler--file-search]"

    def get_queryset(self):
        qs = super().get_queryset().select_related('uploaded_by', 'module')
        if not self.request.user.is_authenticated:
            return qs.none()
        start, end = self._get_selected_month_range()
        return qs.filter(
            uploaded_by__groups__name=GROUP_COACH,
            training_date__range=(start, end),
        ).distinct()


class CompetitorTraininglogListView(
    TraininglogMonthFilterMixin,
    TitleMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    SingleTableView,
):
    """选手训练日志：展示所有“选手”上传的日志。"""

    model = TrainingLog
    table_class = TrainingLogOthersTable
    template_name = "traininglogs/traininglog_list.html"
    permission_required = "traininglogs.view_competitor_traininglog"
    raise_exception = True
    paginate_by = pagination_per_page
    title = "选手训练日志"
    title_icon = "icon-[tabler--file-search]"

    def get_queryset(self):
        qs = super().get_queryset().select_related('uploaded_by', 'module')
        if not self.request.user.is_authenticated:
            return qs.none()
        start, end = self._get_selected_month_range()
        return qs.filter(
            uploaded_by__groups__name=GROUP_COMPETITOR,
            training_date__range=(start, end),
        ).distinct()


class TraininglogMonthlyStatView(
    TraininglogMonthFilterMixin,
    TitleMixin,
    LoginRequiredMixin,
    SingleTableView,
):
    """按月统计提交情况：列为 日期 / 已提交选手 / 未提交选手 / 已提交教练。

    查询参数：
      - year=YYYY（默认当年）
      - month=MM（默认当月）
    仅统计具备 add 权限的用户。
    """

    template_name = 'traininglogs/traininglog_statistics.html'
    table_class = MonthlyStatTable
    model = TrainingLog
    table_pagination = False
    title_icon = 'icon-[tabler--chart-bar]'

    def get_queryset(self):
        return TrainingLog.objects.none()

    def _get_add_perm_users(self, group_name: str):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return (
            User.objects.filter(is_active=True, groups__name=group_name)
            .filter(
                Q(user_permissions__codename="add_traininglog", user_permissions__content_type__app_label="traininglogs")
                | Q(groups__permissions__codename="add_traininglog", groups__permissions__content_type__app_label="traininglogs")
            )
            .distinct()
        )

    def get_table_data(self):
        year, month = self._get_selected_year_month()
        start, end = self._get_selected_month_range()
        today = timezone.localdate()
        if year == today.year and month == today.month:
            end = min(end, today)

        comp_qs = self._get_add_perm_users(GROUP_COMPETITOR)
        coach_qs = self._get_add_perm_users(GROUP_COACH)

        comp_names = {u.id: u.display_name for u in comp_qs}
        coach_names = {u.id: u.display_name for u in coach_qs}
        comp_ids = set(comp_names.keys())
        coach_ids = set(coach_names.keys())

        user_ids = comp_ids | coach_ids
        rows = (
            TrainingLog.objects
            .filter(training_date__range=(start, end), uploaded_by_id__in=user_ids)
            .values_list('training_date', 'uploaded_by_id')
        )

        by_day = {}
        for d, uid in rows:
            by_day.setdefault(d, set()).add(uid)

        data = []
        cur = start
        while cur <= end:
            submitted_ids = by_day.get(cur, set())
            comp_submitted = sorted([comp_names[uid] for uid in submitted_ids if uid in comp_ids])
            coach_submitted = sorted([coach_names[uid] for uid in submitted_ids if uid in coach_ids])
            comp_unsubmitted = sorted([name for uid, name in comp_names.items() if uid not in submitted_ids])

            data.append({
                'date': cur,
                'is_sunday': cur.weekday() == 6,
                'submitted_competitors': " ".join(comp_submitted) or "无",
                'unsubmitted_competitors': " ".join(comp_unsubmitted) or "全部提交",
                'submitted_coaches': " ".join(coach_submitted) or "无",
            })
            cur += timedelta(days=1)
        return data

    def get_title(self):
        year, month = self._get_selected_year_month()
        return f"训练日志提交统计（{year}年{month:02d}月）"
