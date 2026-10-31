# meetings/views.py
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse, QueryDict
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views.generic import CreateView, DetailView, DeleteView, UpdateView
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET
from django.views.decorators.vary import vary_on_headers
from django_tables2 import SingleTableView

from accounts.services.users import get_user_display_name, get_user_full_info
from core.file_preview import (
    FilePreviewMetadata,
    build_download_response,
    build_file_preview_descriptor,
    build_inline_preview_response,
)
from core.utils.mixins import TitleMixin
from core.utils.listing import FilterableListMixin, ListFilterSpec
from core.utils.breadcrumbs import breadcrumb_link
from .forms import MeetingUploadForm, MeetingAudienceForm, MeetingListFilterForm
from .models import Meeting
from .permissions import (
    ADD_MEETING_PERMISSION,
    DELETE_MEETING_PERMISSION,
    CHANGE_MEETING_PERMISSION,
    can_change_meeting_admin,
    can_upload_meeting,
    can_view_meeting,
)
from .services import save_meeting
from .selectors import meeting_queryset_for, recipient_queryset, search_meetings, search_recipients
from .tables import MeetingTable


class MeetingUploadView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = Meeting
    form_class = MeetingUploadForm
    template_name = 'meetings/meeting_form.html'
    success_url = reverse_lazy('meetings:meeting_list')
    permission_required = ADD_MEETING_PERMISSION
    raise_exception = True
    title = "上传会议记录"
    title_icon = "icon-[tabler--calendar-plus]"

    def form_valid(self, form):
        try:
            self.object = save_meeting(
                meeting=form.instance,
                actor=self.request.user,
                is_public=form.cleaned_data["is_public"],
                group_ids=[group.pk for group in form.cleaned_data["visible_groups"]],
                user_ids=[user.pk for user in form.cleaned_data["visible_users"]],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "会议记录上传成功。")
        return redirect("meetings:meeting_list" if can_view_meeting(self.request.user) else "meetings:meeting_upload")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submit_label"] = "上传"
        context["cancel_url"] = reverse("meetings:meeting_list") if can_view_meeting(self.request.user) else ""
        return context


@method_decorator(vary_on_headers("HX-Request"), name="dispatch")
class MeetingListView(FilterableListMixin, PermissionRequiredMixin, TitleMixin, SingleTableView):
    model = Meeting
    table_class = MeetingTable
    template_name = 'meetings/meeting_list.html'
    table_pagination = {"per_page": 20}
    title = "会议记录列表"
    title_icon = "icon-[tabler--calendar-event]"
    permission_required = "meetings.view_meeting"
    list_filter_specs = (
        ListFilterSpec("q", "搜索会议", "search", placeholder="搜索会议名称、文件名、上传者姓名或账号"),
        ListFilterSpec("date_from", "会议起日", "date"),
        ListFilterSpec("date_to", "会议止日", "date"),
    )

    def get_base_queryset(self):
        return meeting_queryset_for(self.request.user).order_by("-date", "-pk")

    def apply_search(self, queryset):
        self.filter_form = MeetingListFilterForm(self.request.GET)
        if not self.filter_form.is_valid():
            return queryset.none()
        return search_meetings(queryset, self.filter_form.cleaned_data["q"])

    def apply_custom_filters(self, queryset):
        if not self.filter_form.is_valid():
            return queryset.none()
        for field, lookup in (("date_from", "date__gte"), ("date_to", "date__lte")):
            if self.filter_form.cleaned_data[field]:
                queryset = queryset.filter(**{lookup: self.filter_form.cleaned_data[field]})
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(filter_form=self.filter_form, can_upload=can_upload_meeting(self.request.user))
        return context


def meeting_return_url(user, raw_query):
    """仅接收列表查询参数；从不接受调用方指定的跳转域名或路径。"""
    parsed = QueryDict(raw_query)
    params = QueryDict(mutable=True)
    for key in ("q", "date_from", "date_to", "sort", "page"):
        if key in parsed:
            params[key] = parsed[key]
    form = MeetingListFilterForm(params)
    queryset = meeting_queryset_for(user)
    if form.is_valid():
        queryset = search_meetings(queryset, form.cleaned_data["q"])
        if form.cleaned_data["date_from"]:
            queryset = queryset.filter(date__gte=form.cleaned_data["date_from"])
        if form.cleaned_data["date_to"]:
            queryset = queryset.filter(date__lte=form.cleaned_data["date_to"])
    else:
        queryset = queryset.none()
    try:
        page = int(params.get("page", "1"))
    except ValueError:
        page = 1
    if "page" in params:
        params["page"] = str(min(max(page, 1), Paginator(queryset, 20).num_pages))
    return reverse("meetings:meeting_list") + ("?" + params.urlencode() if params else "")


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
        metadata = [
            FilePreviewMetadata("会议日期", meeting.date_chinese, is_date=True),
            FilePreviewMetadata("可见范围", "所有人可见" if meeting.is_public else "限定人员可见"),
        ]
        if can_change_meeting_admin(self.request.user, meeting) and not meeting.is_public:
            metadata.extend(
                [
                    FilePreviewMetadata(
                        "可见角色", "、".join(meeting.visible_groups.values_list("name", flat=True)) or "—"
                    ),
                    FilePreviewMetadata(
                        "指定人员", "、".join(get_user_full_info(user) for user in meeting.visible_users.all()) or "—"
                    ),
                ]
            )
        context["file_preview"] = build_file_preview_descriptor(
            file=meeting.file,
            filename=meeting.filename,
            download_url=reverse("meetings:meeting_file", args=[meeting.pk]),
            preview_url=reverse("meetings:meeting_pdf_inline", args=[meeting.pk]),
            uploader_name=(get_user_display_name(meeting.uploaded_by) if meeting.uploaded_by_id else "—"),
            uploaded_at=meeting.uploaded_at,
            source_label="会议记录列表",
            source_url=reverse("meetings:meeting_list"),
            title=meeting.title,
            metadata=tuple(metadata),
        )
        return context


class MeetingFileContentView(MeetingAccessMixin, DetailView):
    def get(self, request, *args, **kwargs):
        meeting = self.get_object()
        return build_download_response(meeting.file, meeting.filename)


class MeetingDeleteView(PermissionRequiredMixin, MeetingAccessMixin, DeleteView):
    model = Meeting
    success_url = reverse_lazy('meetings:meeting_list')
    permission_required = DELETE_MEETING_PERMISSION
    raise_exception = True


class MeetingAudienceView(PermissionRequiredMixin, TitleMixin, MeetingAccessMixin, UpdateView):
    form_class = MeetingAudienceForm
    template_name = "meetings/meeting_form.html"
    permission_required = CHANGE_MEETING_PERMISSION
    raise_exception = True
    title = "设置可见人员"
    title_icon = "icon-[tabler--users]"

    def form_valid(self, form):
        try:
            self.object = save_meeting(
                meeting=form.instance,
                actor=self.request.user,
                change=True,
                audience_only=True,
                is_public=form.cleaned_data["is_public"],
                group_ids=[group.pk for group in form.cleaned_data["visible_groups"]],
                user_ids=[user.pk for user in form.cleaned_data["visible_users"]],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "可见人员已保存。")
        return redirect(meeting_return_url(self.request.user, self.request.GET.get("return_query", "")))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            submit_label="保存",
            cancel_url=meeting_return_url(self.request.user, self.request.GET.get("return_query", "")),
        )
        return context

    def get_breadcrumb_parents(self):
        return [breadcrumb_link("会议记录列表", "meetings:meeting_list")]


@require_GET
def recipient_search(request):
    meeting_id = request.GET.get("meeting_id", "")
    if meeting_id:
        if not can_change_meeting_admin(request.user):
            raise PermissionDenied
        if not meeting_id.isdecimal():
            return JsonResponse({"error": "会议编号无效。"}, status=400)
        get_object_or_404(meeting_queryset_for(request.user), pk=meeting_id)
    elif not can_upload_meeting(request.user):
        raise PermissionDenied
    query = request.GET.get("q", "").strip()
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 0
    if page < 1 or (page - 1) * 20 > 2**63 - 1 or len(query) > 100:
        return JsonResponse({"error": "搜索条件无效，请重新输入。"}, status=400)
    users = list(search_recipients(recipient_queryset(), query)[(page - 1) * 20 : page * 20 + 1]) if query else []
    response = JsonResponse(
        {
            "results": [{"id": user.pk, "label": get_user_full_info(user)} for user in users[:20]],
            "has_more": len(users) > 20,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response
