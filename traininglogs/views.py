# traininglogs/views.py
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
)
from django.http import Http404
from django.views.generic import CreateView, DetailView, DeleteView
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django_tables2 import SingleTableView

from .models import TrainingLog
from .forms import TrainingLogCreateForm
from core.utils.pdf_response import pdf_inline_response
from .tables import TrainingLogTable, TrainingLogOthersTable, MonthlyStatTable


pagination_per_page = 18


# 训练日志上传视图
class TrainingLogUploadView(PermissionRequiredMixin, CreateView):
    model = TrainingLog
    form_class = TrainingLogCreateForm
    template_name = "traininglogs/traininglog_upload.html"
    success_url = reverse_lazy("traininglogs:traininglog_list")
    permission_required = "traininglogs.add_traininglog"
    raise_exception = True
    extra_context = {
        "title": "上传训练日志",
        "title_icon": "icon-[tabler--upload]",
    }

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, "训练日志上传成功！")
        return super().form_valid(form)


# 训练日志列表视图
class TraininglogListView(LoginRequiredMixin, SingleTableView):
    model = TrainingLog
    table_class = TrainingLogTable
    template_name = "traininglogs/traininglog_list.html"
    # table_pagination = {"per_page": 10}  # 每页显示31条记录
    paginate_by = pagination_per_page
    extra_context = {
        "title": "我的训练日志",
        "title_icon": "icon-[tabler--file-stack]",
    }

    def get_queryset(self):
        # 只显示当前登录用户自己的日志
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            return qs.filter(uploaded_by=self.request.user)
        return qs.none()


def traininglog_pdf_inline(request, pk):
    # 仅允许查看自己的日志
    tl = get_object_or_404(TrainingLog, pk=pk)
    user = request.user
    if not user.is_authenticated:
        raise Http404("无法预览该PDF文件。")
    # 超管放行；本人放行；选手可看教练；教练可看选手
    if getattr(user, "is_superuser", False):
        pass
    else:
        owner_id = getattr(tl, "uploaded_by_id", None)
        if owner_id == getattr(user, "pk", None):
            pass
        else:
            owner_user = getattr(tl, "uploaded_by", None)
            owner_groups = (
                set(owner_user.groups.values_list("name", flat=True))
                if owner_user is not None
                else set()
            )
            user_groups = (
                set(getattr(user, "groups").values_list("name", flat=True))
                if getattr(user, "pk", None)
                else set()
            )
            allow = ("选手" in user_groups and "教练" in owner_groups) or (
                "教练" in user_groups and "选手" in owner_groups
            )
            if not allow:
                raise Http404("无法预览该PDF文件。")
    resp = pdf_inline_response(tl.file.path, filename=tl.filename)
    if resp is None:
        raise Http404("无法预览该PDF文件。")
    return resp


class TrainingLogDetailView(LoginRequiredMixin, DetailView):
    model = TrainingLog
    template_name = "traininglogs/traininglog_detail.html"
    context_object_name = "traininglog"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        # 超管放行；本人放行；选手可看教练；教练可看选手
        if getattr(user, "is_superuser", False):
            return obj
        if getattr(obj, "uploaded_by_id", None) == getattr(user, "pk", None):
            return obj
        owner_user = getattr(obj, "uploaded_by", None)
        owner_groups = (
            set(owner_user.groups.values_list("name", flat=True))
            if owner_user is not None
            else set()
        )
        user_groups = (
            set(getattr(user, "groups").values_list("name", flat=True))
            if getattr(user, "pk", None)
            else set()
        )
        allow = ("选手" in user_groups and "教练" in owner_groups) or (
            "教练" in user_groups and "选手" in owner_groups
        )
        if not allow:
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pdf_preview_url"] = reverse(
            "traininglogs:traininglog_pdf_inline", args=[self.object.pk]   # type: ignore
        )  # type: ignore
        return context


class TrainingLogDeleteView(LoginRequiredMixin, DeleteView):
    model = TrainingLog
    # template_name = "traininglogs/traininglog_confirm_delete.html"
    success_url = reverse_lazy("traininglogs:traininglog_list")
    # permission_required = 'traininglogs.delete_traininglog'
    raise_exception = True

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # 仅允许删除自己的
        if getattr(obj, "uploaded_by_id", None) != getattr(
            self.request.user, "pk", None
        ):
            raise Http404
        return obj


class CoachTraininglogListView(
    LoginRequiredMixin, PermissionRequiredMixin, SingleTableView
):
    """教练训练日志：展示所有“教练”上传的日志。"""

    model = TrainingLog
    table_class = TrainingLogOthersTable
    template_name = "traininglogs/traininglog_list.html"
    permission_required = "traininglogs.view_coach_traininglog"
    raise_exception = True
    # table_pagination = {"per_page": 31}
    paginate_by = pagination_per_page
    extra_context = {
        "title": "教练训练日志",
        "title_icon": "icon-[tabler--file-search]",
    }

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        return qs.filter(uploaded_by__groups__name="教练").distinct()


class CompetitorTraininglogListView(
    LoginRequiredMixin, PermissionRequiredMixin, SingleTableView
):
    """选手训练日志：展示所有“选手”上传的日志。"""

    model = TrainingLog
    table_class = TrainingLogOthersTable
    template_name = "traininglogs/traininglog_list.html"
    permission_required = "traininglogs.view_competitor_traininglog"
    raise_exception = True
    # table_pagination = {"per_page": 10}
    paginate_by = pagination_per_page
    extra_context = {
        "title": "选手训练日志",
        "title_icon": "icon-[tabler--file-search]",
    }

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        return qs.filter(uploaded_by__groups__name="选手").distinct()



class TraininglogMonthlyStatView(LoginRequiredMixin, SingleTableView):
    """按月统计提交情况：列为 日期 / 已提交选手 / 未提交选手 / 已提交教练。

    查询参数：
      - year=YYYY（默认当年）
      - month=MM（默认当月）
    仅统计具备 add 权限的用户。
    """

    template_name = 'traininglogs/traininglog_statistics.html'
    table_class = MonthlyStatTable
    # 为 ListView 提供占位 QuerySet（实际数据来自 get_table_data）
    model = TrainingLog
    # 不分页：一个月内按天展示
    table_pagination = False

    def get_queryset(self):
        return TrainingLog.objects.none()

    def _get_selected_year_month(self):
        from django.utils import timezone
        today = timezone.localdate()
        try:
            year = int(self.request.GET.get('year') or today.year)
        except ValueError:
            year = today.year
        try:
            month = int(self.request.GET.get('month') or today.month)
        except ValueError:
            month = today.month
        if month < 1 or month > 12:
            month = today.month
        return year, month

    def _get_add_perm_users(self, group_name: str):
        # 仅返回属于指定分组且拥有 add_traininglog 权限（来自个人或所在分组）的活跃用户
        from django.contrib.auth import get_user_model
        from django.db.models import Q

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
        from datetime import date, timedelta
        from calendar import monthrange
        from django.utils import timezone

        year, month = self._get_selected_year_month()
        days_in_month = monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, days_in_month)
        # 若为当前月，只显示到今天
        today = timezone.localdate()
        if year == today.year and month == today.month:
            end = min(end, today)

        # 只统计具有 add 权限的选手与教练
        comp_qs = self._get_add_perm_users('选手').values('id', 'first_name', 'username')
        coach_qs = self._get_add_perm_users('教练').values('id', 'first_name', 'username')

        # id -> name（优先显示 first_name）
        comp_names = {u['id']: (u['first_name'] or u['username']) for u in comp_qs}
        coach_names = {u['id']: (u['first_name'] or u['username']) for u in coach_qs}
        comp_ids = set(comp_names.keys())
        coach_ids = set(coach_names.keys())

        # 当月日志，仅关心上述用户
        user_ids = comp_ids | coach_ids
        rows = (
            TrainingLog.objects
            .filter(training_date__range=(start, end), uploaded_by_id__in=user_ids)
            .values_list('training_date', 'uploaded_by_id')
        )

        # d -> set(user_id)
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

    def get_context_data(self, **kwargs):
        from django.utils import timezone
        ctx = super().get_context_data(**kwargs)
        year, month = self._get_selected_year_month()
        # 下拉月份（近 12 个月，倒序，最近在上）
        t = timezone.localdate()
        y, m = t.year, t.month
        months = []
        for _ in range(12):
            months.append({'year': y, 'month': m, 'name': f"{y}年{m:02d}月"})
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        ctx.update({
            'title': f"训练日志提交统计（{year}年{month:02d}月）",
            'title_icon': 'icon-[tabler--chart-bar]',
            'months': months,
            'selected_year': year,
            'selected_month': month,
        })
        return ctx
