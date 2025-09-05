# traininglogs/views.py
from django.views.generic import  CreateView, DetailView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect

from .models import TrainingLog
from .forms import TrainingLogCreateForm
from common.mixins import TableListView, TitleMixin
from common.utils.pdf_response import pdf_inline_response

# 训练日志上传视图
class TrainingLogUploadView(CreateView):
    model = TrainingLog
    form_class = TrainingLogCreateForm
    template_name = 'traininglogs/traininglog_upload.html'
    success_url = reverse_lazy('traininglogs:traininglog_list')
    extra_context = {
        'title': '上传训练日志',
        'title_icon': 'icon-[tabler--upload]',
    }

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, "训练日志上传成功！")
        return super().form_valid(form)

# 训练日志列表视图
class TrainingLogListView(TableListView):
    model = TrainingLog
    template_name = 'traininglogs/traininglog_list.html'
    paginate_by = 20  # 每页显示20条记录

    context_object_name = 'traininglogs'
    extra_context = {
        "title" : "训练日志列表",
        "icon" : "icon-[tabler--file-stack]"
    }

    table_headers = ["训练日期", "训练模块", "训练任务", "文件名", "上传者", "上传时间", "操作"]
    table_sort_map = {
        "训练日期": "training_date",
        "训练模块": "module__name",
        "训练任务": "task",
        "上传者": "uploaded_by__username",
        "上传时间": "uploaded_at",
    }
    search_fields = ["task", "module__name", "uploaded_by__username"]
    default_sort = "-training_date"

    def get_table_rows(self, queryset) -> list[list]:
        rows = []
        for log in queryset:
            btn = self.fmt_btn(reverse_lazy('traininglogs:traininglog_detail', args=[log.pk]), "查看", size="xs")
            module_name = log.module.name if getattr(log, 'module', None) else "Unknown"
            # uploaded_by 允许为空
            if log.uploaded_by:
                uploader = log.uploaded_by.first_name or log.uploaded_by.username
            else:
                uploader = "Unknown"
            rows.append([
                log.training_date.strftime('%Y-%m-%d'),
                module_name,
                log.task,
                getattr(log, 'filename', getattr(log.file, 'name', '')),
                uploader,
                log.uploaded_at.strftime('%Y-%m-%d %H:%M'),
                btn,
            ])
        return rows
    

# 供下载或在线查看 PDF 文件
def traininglog_pdf_inline(request, pk):
    log = get_object_or_404(TrainingLog, pk=pk)
    if not log.file:
        messages.error(request, "该训练日志没有关联文件。")
        return redirect('traininglogs:traininglog_list')
    return pdf_inline_response(log.file.path, filename=log.filename)  # type: ignore


# 训练日志详情视图
class TrainingLogDetailView(TitleMixin, DetailView):
    model = TrainingLog
    template_name = 'traininglogs/traininglog_detail.html'
    context_object_name = 'traininglog'
    title_object_fields = ['uploaded_at', 'uploaded_by', 'module']
    title_template = "{uploaded_by}{uploaded_at:%Y年%m月%d日}{module}模块训练日志"
    title_icon = "icon-[tabler--file-text]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 在运行时生成PDF预览URL，避免循环导入
        context['pdf_preview_url'] = reverse('traininglogs:traininglog_pdf_inline', args=[self.object.pk])  # type: ignore
        return context


    

    