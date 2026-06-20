from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from core.utils.mixins import TitleMixin

from .forms import DemoProfileForm, DemoUploadForm


@dataclass(frozen=True)
class DemoRecord:
    code: str
    name: str
    owner: str
    status: str
    score: int


DEMO_RECORDS = [
    DemoRecord("TMS-001", "Linux 基础训练", "教练组 A", "进行中", 86),
    DemoRecord("TMS-002", "Windows 服务考核", "教练组 B", "待评审", 74),
    DemoRecord("TMS-003", "网络排障演练", "教练组 A", "已归档", 92),
    DemoRecord("TMS-004", "安全加固任务", "教练组 C", "进行中", 81),
    DemoRecord("TMS-005", "自动化脚本训练", "教练组 A", "待评审", 68),
    DemoRecord("TMS-006", "综合模拟赛", "专家组", "进行中", 89),
]


class DemoBaseView(TitleMixin, TemplateView):
    """开发模式专用 demo 视图基类。"""

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEBUG:
            raise Http404("Demo pages are only available in development mode")
        return super().dispatch(request, *args, **kwargs)


class DashboardView(DemoBaseView):
    template_name = "demo/index.html"
    title = "UI 验收中心"
    title_icon = "icon-[tabler--components]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cards"] = [
            {"label": "布局", "value": 6, "hint": "base/app/minimal/auth/print/htmx", "icon": "icon-[tabler--layout-dashboard]"},
            {"label": "组件", "value": 16, "hint": "按钮、表单、表格、弹窗等", "icon": "icon-[tabler--blocks]"},
            {"label": "HTMX", "value": 3, "hint": "局部刷新示例", "icon": "icon-[tabler--arrows-transfer-up]"},
        ]
        return context


class ListDemoView(DemoBaseView):
    template_name = "demo/list.html"
    title = "普通列表页"
    title_icon = "icon-[tabler--list-details]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "").strip()
        records = DEMO_RECORDS
        if query:
            records = [record for record in records if query.lower() in record.name.lower() or query.lower() in record.code.lower()]
        if status:
            records = [record for record in records if record.status == status]
        paginator = Paginator(records, 3)
        context["records"] = paginator.get_page(self.request.GET.get("page"))
        context["query"] = query
        context["status"] = status
        context["statuses"] = ["进行中", "待评审", "已归档"]
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        template_name = "demo/list.html#results" if request.htmx else self.template_name
        return render(request, template_name, context)


class HtmxDemoView(ListDemoView):
    title = "HTMX 筛选分页"
    title_icon = "icon-[tabler--refresh]"


class FormDemoView(DemoBaseView):
    template_name = "demo/form.html"
    title = "表单页"
    title_icon = "icon-[tabler--forms]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", DemoProfileForm())
        return context

    def post(self, request, *args, **kwargs):
        form = DemoProfileForm(request.POST)
        context = self.get_context_data(form=form)
        if form.is_valid():
            messages.success(request, "表单提交成功。")
        template_name = "demo/form.html#form_body" if request.htmx else self.template_name
        return render(request, template_name, context)


class DetailDemoView(DemoBaseView):
    template_name = "demo/detail.html"
    title = "详情页"
    title_icon = "icon-[tabler--file-description]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["record"] = DEMO_RECORDS[0]
        return context


class UploadDemoView(View):
    template_name = "demo/upload.html"

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEBUG:
            raise Http404("Demo pages are only available in development mode")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {"title": "文件上传组件", "title_icon": "icon-[tabler--upload]", "form": DemoUploadForm()})

    def post(self, request):
        form = DemoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            messages.success(request, "文件上传表单校验通过。")
        template_name = "demo/upload.html#file_field" if request.htmx else self.template_name
        return render(request, template_name, {"title": "文件上传组件", "title_icon": "icon-[tabler--upload]", "form": form})


class PrintDemoView(DemoBaseView):
    template_name = "demo/print.html"
    title = "打印页"
    title_icon = "icon-[tabler--printer]"


class StatesDemoView(DemoBaseView):
    template_name = "demo/states.html"
    title = "状态与弹窗"
    title_icon = "icon-[tabler--alert-square-rounded]"

    def post(self, request, *args, **kwargs):
        messages.info(request, "确认弹窗提交成功。")
        return self.get(request, *args, **kwargs)
