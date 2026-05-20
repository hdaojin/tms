# meetings/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import CreateView, DetailView, DeleteView
from django.urls import reverse_lazy, reverse
from django_tables2 import SingleTableView

from .forms import MeetingUploadForm
from .models import Meeting
from .permissions import (
    ADD_MEETING_PERMISSION,
    DELETE_MEETING_PERMISSION,
    can_view_meeting,
    can_view_meeting_request,
)
from .services import prepare_meeting_for_save
from .tables import MeetingTable
from core.utils.mixins import TitleMixin
from core.utils.pdf_response import create_pdf_preview_view


class MeetingUploadView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = Meeting
    form_class = MeetingUploadForm
    template_name = 'meetings/upload_meeting.html'
    success_url = reverse_lazy('meetings:meeting_list')
    permission_required = ADD_MEETING_PERMISSION
    raise_exception = True
    title = "上传会议记录"
    title_icon = "icon-[tabler--calendar-plus]"
    
    def form_valid(self, form):
        prepare_meeting_for_save(form.instance, actor=self.request.user, change=False)
        return super().form_valid(form)


class MeetingListView(LoginRequiredMixin, TitleMixin, SingleTableView):
    model = Meeting
    table_class = MeetingTable
    template_name = 'meetings/meeting_list.html'
    table_pagination = {"per_page": 20}
    title = "会议记录列表"
    title_icon = "icon-[tabler--calendar-event]"

    def get_queryset(self):
        queryset = super().get_queryset().select_related('uploaded_by')
        if not can_view_meeting(self.request.user):
            return queryset.none()
        return queryset


# 使用工厂函数创建 PDF 预览视图（会议记录登录后即可预览）
meeting_pdf_inline = create_pdf_preview_view(Meeting, permission_checker=can_view_meeting_request)


class MeetingDetailView(LoginRequiredMixin, TitleMixin, DetailView):
    model = Meeting
    template_name = 'meetings/meeting_detail.html'
    context_object_name = 'meeting'
    title = "{date_chinese}的{title}会议记录"
    title_icon = "icon-[tabler--file-text]"

    def get_queryset(self):
        queryset = super().get_queryset().select_related('uploaded_by')
        if not can_view_meeting(self.request.user):
            return queryset.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pdf_preview_url'] = reverse('meetings:meeting_pdf_inline', args=[self.object.pk])  # type: ignore
        return context


class MeetingDeleteView(PermissionRequiredMixin, DeleteView):
    model = Meeting
    success_url = reverse_lazy('meetings:meeting_list')
    permission_required = DELETE_MEETING_PERMISSION
    raise_exception = True