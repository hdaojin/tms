# meetings/views.py
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import FileResponse, Http404
from django.views.generic import CreateView, DetailView, DeleteView
from django.urls import reverse_lazy
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
from core.utils.mixins import PdfPreviewDetailMixin, TitleMixin, UploadedDocumentCreateMixin
from core.utils.pdf_response import create_pdf_preview_view


class MeetingUploadView(UploadedDocumentCreateMixin, TitleMixin, PermissionRequiredMixin, CreateView):
    model = Meeting
    form_class = MeetingUploadForm
    template_name = 'common/document_upload_form.html'
    success_url = reverse_lazy('meetings:meeting_list')
    permission_required = ADD_MEETING_PERMISSION
    raise_exception = True
    title = "上传会议记录"
    title_icon = "icon-[tabler--calendar-plus]"

    def prepare_document_for_save(self, form):
        prepare_meeting_for_save(form.instance, actor=self.request.user, change=False)


class MeetingListView(PermissionRequiredMixin, TitleMixin, SingleTableView):
    model = Meeting
    table_class = MeetingTable
    template_name = 'meetings/meeting_list.html'
    table_pagination = {"per_page": 20}
    title = "会议记录列表"
    title_icon = "icon-[tabler--calendar-event]"
    permission_required = "meetings.view_meeting"

    def get_queryset(self):
        queryset = super().get_queryset().select_related('uploaded_by')
        if not can_view_meeting(self.request.user):
            return queryset.none()
        return queryset


# 使用工厂函数创建 PDF 预览视图（会议记录登录后即可预览）
meeting_pdf_inline = create_pdf_preview_view(Meeting, permission_checker=can_view_meeting_request)


class MeetingDetailView(PermissionRequiredMixin, PdfPreviewDetailMixin, TitleMixin, DetailView):
    model = Meeting
    template_name = 'common/document_detail_with_pdf.html'
    context_object_name = 'meeting'
    pdf_preview_url_name = 'meetings:meeting_pdf_inline'
    title = "{date_chinese}的{title}会议记录"
    title_icon = "icon-[tabler--file-text]"
    permission_required = "meetings.view_meeting"

    def get_queryset(self):
        queryset = super().get_queryset().select_related('uploaded_by')
        if not can_view_meeting(self.request.user):
            return queryset.none()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["document_download_url"] = reverse_lazy(
            "meetings:meeting_file", args=[self.object.pk]
        )
        return context


class MeetingFileContentView(PermissionRequiredMixin, DetailView):
    model = Meeting
    permission_required = "meetings.view_meeting"

    def get(self, request, *args, **kwargs):
        meeting = self.get_object()
        if not meeting.file:
            raise Http404
        return FileResponse(
            meeting.file.open("rb"),
            as_attachment=True,
            filename=meeting.filename,
        )


class MeetingDeleteView(PermissionRequiredMixin, DeleteView):
    model = Meeting
    success_url = reverse_lazy('meetings:meeting_list')
    permission_required = DELETE_MEETING_PERMISSION
    raise_exception = True
