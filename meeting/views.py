from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth.decorators import permission_required  # 如果使用函数视图
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.core.files.base import ContentFile
from django.http import FileResponse
from django.views.generic import CreateView, ListView, DetailView
from django.urls import reverse_lazy

from pathlib import Path

from .forms import MeetingUploadForm
from .models import Meeting

class MeetingUploadView(PermissionRequiredMixin, CreateView):
    model = Meeting
    form_class = MeetingUploadForm
    template_name = 'meeting/upload_meeting.html'
    success_url = reverse_lazy('meeting:meeting_list')
    permission_required = 'meeting.add_meeting'
    raise_exception = True  # 如果没有权限则抛出403错误

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        file_extension = Path(form.instance.upload.name).suffix.lower()
        form.instance.filename = f"{form.instance.date.strftime('%Y.%m.%d')}-{form.instance.title}{file_extension}"
        return super().form_valid(form)


class MeetingListView(ListView):
    model = Meeting
    template_name = 'meeting/meeting_list.html'
    context_object_name = 'meetings'
    ordering = ['-date']
    paginate_by = 20  # 每页显示10条记录
    

class MeetingDetailView(DetailView):
    model = Meeting
    template_name = 'meeting/meeting_detail.html'
    context_object_name = 'meeting'




    