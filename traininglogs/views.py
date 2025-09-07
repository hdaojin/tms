# traininglogs/views.py
from django.views.generic import  CreateView, DetailView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django_tables2 import SingleTableView

from .models import TrainingLog
from .forms import TrainingLogCreateForm
from common.utils.pdf_response import pdf_inline_response
from .tables import TrainingLogTable

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
class TraininglogListView(SingleTableView):
    model = TrainingLog
    table_class = TrainingLogTable
    template_name = 'traininglogs/traininglog_list.html'
    table_pagination = {"per_page": 20}  # 每页显示20条记录
    extra_context = {
        'title': "训练日志列表",
        'title_icon': "icon-[tabler--file-stack]",
    }