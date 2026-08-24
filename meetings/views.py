# meetings/views.py
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, DetailView, DeleteView
from django.urls import reverse, reverse_lazy
from django_tables2 import SingleTableView

from accounts.services.users import get_user_display_name
from core.file_preview import (
    FilePreviewMetadata,
    build_download_response,
    build_file_preview_descriptor,
    build_inline_preview_response,
)
from core.utils.mixins import TitleMixin, UploadedDocumentCreateMixin
from .forms import MeetingUploadForm
from .models import Meeting
from .permissions import (
    ADD_MEETING_PERMISSION,
    DELETE_MEETING_PERMISSION,
    can_view_meeting,
)
from .services import prepare_meeting_for_save
from .tables import MeetingTable


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


def meeting_queryset_for(user):
    queryset = Meeting.objects.select_related("uploaded_by")
    if not can_view_meeting(user):
        return queryset.none()
    return queryset


class MeetingAccessMixin:
    model = Meeting

    def get_queryset(self):
        return meeting_queryset_for(self.request.user)


def meeting_pdf_inline(request, pk):
    meeting = get_object_or_404(meeting_queryset_for(request.user), pk=pk)
    return build_inline_preview_response(meeting.file, meeting.filename)


class MeetingDetailView(TitleMixin, MeetingAccessMixin, DetailView):
    model = Meeting
    template_name = "common/file_preview_detail.html"
    context_object_name = "meeting"
    title = "{date_chinese}的{title}会议记录"
    title_icon = "icon-[tabler--file-text]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        meeting = self.object
        context["file_preview"] = build_file_preview_descriptor(
            file=meeting.file,
            filename=meeting.filename,
            download_url=reverse("meetings:meeting_file", args=[meeting.pk]),
            preview_url=reverse("meetings:meeting_pdf_inline", args=[meeting.pk]),
            uploader_name=(
                get_user_display_name(meeting.uploaded_by) if meeting.uploaded_by_id else "—"
            ),
            uploaded_at=meeting.uploaded_at,
            source_label="会议记录列表",
            source_url=reverse("meetings:meeting_list"),
            title=meeting.title,
            metadata=(FilePreviewMetadata("会议日期", meeting.date_chinese),),
        )
        return context


class MeetingFileContentView(MeetingAccessMixin, DetailView):

    def get(self, request, *args, **kwargs):
        meeting = self.get_object()
        return build_download_response(meeting.file, meeting.filename)


class MeetingDeleteView(PermissionRequiredMixin, DeleteView):
    model = Meeting
    success_url = reverse_lazy('meetings:meeting_list')
    permission_required = DELETE_MEETING_PERMISSION
    raise_exception = True
