# from django.contrib.auth.decorators import permission_required  # 如果使用函数视图
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import  Http404
from django.views.generic import CreateView, DetailView, ListView
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404
from django_tables2 import SingleTableView
from .tables import MeetingTable


from .forms import MeetingUploadForm
from .models import Meeting
from common.mixins import TitleMixin, TableListView
from common.utils.pdf_response import pdf_inline_response


class MeetingUploadView(PermissionRequiredMixin, TitleMixin, CreateView):
    model = Meeting
    form_class = MeetingUploadForm
    template_name = 'meeting/upload_meeting.html'
    success_url = reverse_lazy('meeting:meeting_list')
    permission_required = 'meeting.add_meeting'
    raise_exception = True  # 如果没有权限则抛出403错误

    title = "上传会议记录"
    title_icon = "icon-[tabler--upload]"
    
    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)


class MeetingListView(SingleTableView):
    model = Meeting
    table_class = MeetingTable
    template_name = 'meeting/meeting_list.html'
    table_pagination = {"per_page": 20}  # 每页显示20条记录
    extra_context = {
        'title': "会议记录列表",
        'title_icon': "icon-[tabler--file-stack]",
    }



"""
class MeetingListView(TitleMixin, TableListView):
    model = Meeting
    template_name = 'meeting/meeting_list.html'
    paginate_by = 20  # 每页显示10条记录

    context_object_name = 'meetings'
    title = "会议记录列表"
    title_icon = "icon-[tabler--file-stack]"

    table_headers = ["会议日期", "会议名称", "文件名", "上传者", "上传时间", "操作"]
    table_sort_map = {
        "会议日期": "date",
        "会议名称": "title",
        "上传者": "uploaded_by__username",
        "上传时间": "uploaded_at",
    }
    search_fields = ["title", "uploaded_by__username"]
    default_sort = "-date"

    def get_table_rows(self, queryset) -> list[list]:
        rows = []
        for meeting in queryset:
            btn = self.fmt_btn(reverse('meeting:meeting_detail', args=[meeting.pk]), "查看", size="xs")
            rows.append([
                meeting.date.strftime('%Y-%m-%d'),
                meeting.title,
                meeting.filename,
                meeting.uploaded_by.first_name if meeting.uploaded_by.first_name else meeting.uploaded_by.username,
                meeting.uploaded_at.strftime('%Y-%m-%d %H:%M'),
                btn,
            ])
        return rows
"""          


def meeting_pdf_inline(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    pdf_inline_response_obj = pdf_inline_response(meeting.file.path, filename=meeting.filename)
    if pdf_inline_response_obj is None:
        raise Http404("无法预览该PDF文件。")
    return pdf_inline_response_obj


class MeetingDetailView(TitleMixin, DetailView):
    model = Meeting
    template_name = 'meeting/meeting_detail.html'
    context_object_name = 'meeting'
    title_object_fields = ['date_chinese', 'title']
    # title_separator = ' - '
    title_template = "{date_chinese}的{title}会议记录"
    title_icon = "icon-[tabler--file-text]"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 在运行时生成PDF预览URL，避免循环导入
        context['pdf_preview_url'] = reverse('meeting:meeting_pdf_inline', args=[self.object.pk])  # type: ignore
        return context