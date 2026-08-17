from __future__ import annotations

import mimetypes
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from core.utils.listing import FilterableListMixin
from core.utils.mixins import TitleMixin

from .forms import FeedbackForm, FeedbackManageForm, FeedbackReplyForm
from .models import Feedback, FeedbackAttachment, FeedbackCategory, FeedbackStatus, sanitize_original_filename
from .permissions import (
    can_manage_feedback,
    can_reply_feedback,
    can_view_anonymous_identity,
    can_view_feedback,
)
from .selectors import feedback_detail_for, visible_feedbacks_for
from .services import add_feedback_reply, create_feedback, update_feedback_status


def _detail_context(request: HttpRequest, feedback: Feedback, *, reply_form=None, manage_form=None) -> dict:
    if reply_form is None:
        reply_form = FeedbackReplyForm()
    if manage_form is None and can_manage_feedback(request.user):
        manage_form = FeedbackManageForm(
            initial={"status": feedback.status, "resolution": feedback.resolution}
        )
    return {
        "feedback": feedback,
        "reply_form": reply_form,
        "manage_form": manage_form,
        "title": "反馈详情",
        "title_icon": "icon-[tabler--message-report]",
        "can_reply": can_reply_feedback(request.user, feedback),
        "can_manage": can_manage_feedback(request.user),
        "can_view_anonymous_identity": can_view_anonymous_identity(request.user),
    }


class FeedbackListView(TitleMixin, LoginRequiredMixin, FilterableListMixin, ListView):
    template_name = "feedback/feedback_list.html"
    title = "意见反馈"
    title_icon = "icon-[tabler--message-report]"
    paginate_by = 20

    search_fields = ("title", "content")
    filter_fields = {"category": "category", "status": "status"}
    filter_choices = {
        "category": FeedbackCategory.choices,
        "status": FeedbackStatus.choices,
    }
    extra_filter_params = ("scope",)
    list_filter_target_id = "feedback-list"
    list_filter_indicator_id = "feedback-filter-indicator"
    list_filter_controls_template = "feedback/feedback_list.html#filter-controls"
    list_filter_trigger = (
        "submit, change from:.feedback-filter-select, input changed delay:400ms "
        "from:#feedback-search, search from:#feedback-search"
    )
    list_filter_form_class = "rounded-box border border-base-300 bg-base-100 p-3 shadow-sm"

    def get_base_queryset(self):
        return visible_feedbacks_for(self.request.user)

    def apply_custom_filters(self, queryset):
        if self.request.GET.get("scope") == "my":
            queryset = queryset.filter(author_id=self.request.user.pk)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = context["list_filters"]
        context.update(
            {
                "category_choices": FeedbackCategory.choices,
                "status_choices": FeedbackStatus.choices,
                "selected_category": filters["category"],
                "selected_status": filters["status"],
                "selected_query": filters["q"],
                "selected_scope": filters["scope"],
                "page_actions": [
                    {
                        "label": "提交反馈",
                        "href": reverse("feedback:create"),
                        "icon": "icon-[tabler--message-plus]",
                        "variant_class": "btn btn-primary btn-soft btn-sm",
                    }
                ],
            }
        )
        return context


class FeedbackCreateView(TitleMixin, LoginRequiredMixin, FormView):
    template_name = "feedback/feedback_form.html"
    form_class = FeedbackForm
    title = "提交反馈"
    title_icon = "icon-[tabler--message-plus]"

    def form_valid(self, form):
        try:
            feedback = create_feedback(
                data={
                    "category": form.cleaned_data["category"],
                    "title": form.cleaned_data["title"],
                    "content": form.cleaned_data["content"],
                    "is_anonymous": form.cleaned_data["is_anonymous"],
                    "is_private": form.cleaned_data["is_private"],
                },
                attachments=form.cleaned_data.get("attachments", []),
                actor=self.request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, f"反馈 #{feedback.pk} 已提交。")
        return redirect("feedback:detail", pk=feedback.pk)


class FeedbackDetailView(TitleMixin, LoginRequiredMixin, TemplateView):
    template_name = "feedback/feedback_detail.html"
    title = "反馈详情"
    title_icon = "icon-[tabler--message-report]"

    def get_object(self):
        return feedback_detail_for(self.request.user, self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        feedback = self.get_object()
        context = super().get_context_data(**kwargs)
        context.update(_detail_context(self.request, feedback))
        return context


class FeedbackReplyView(LoginRequiredMixin, View):
    def post(self, request, pk):
        feedback = feedback_detail_for(request.user, pk)
        form = FeedbackReplyForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                add_feedback_reply(
                    feedback=feedback,
                    content=form.cleaned_data["content"],
                    attachments=form.cleaned_data.get("attachments", []),
                    actor=request.user,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "回复已添加。")
                return redirect("feedback:detail", pk=feedback.pk)
        return render(
            request,
            "feedback/feedback_detail.html",
            _detail_context(request, feedback, reply_form=form),
            status=400,
        )


class FeedbackManageView(TitleMixin, LoginRequiredMixin, View):
    title = "处理反馈"
    title_icon = "icon-[tabler--adjustments]"

    def _get_feedback(self, request, pk):
        feedback = feedback_detail_for(request.user, pk)
        if not can_manage_feedback(request.user):
            raise PermissionDenied("当前用户不能管理意见反馈。")
        return feedback

    def get(self, request, pk):
        feedback = self._get_feedback(request, pk)
        form = FeedbackManageForm(initial={"status": feedback.status, "resolution": feedback.resolution})
        return render(
            request,
            "feedback/feedback_manage.html",
            {"feedback": feedback, "form": form, "title": self.title, "title_icon": self.title_icon},
        )

    def post(self, request, pk):
        feedback = self._get_feedback(request, pk)
        form = FeedbackManageForm(request.POST)
        if form.is_valid():
            try:
                update_feedback_status(
                    feedback=feedback,
                    status=form.cleaned_data["status"],
                    resolution=form.cleaned_data["resolution"],
                    actor=request.user,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "反馈处理状态已更新。")
                return redirect("feedback:detail", pk=feedback.pk)
        return render(
            request,
            "feedback/feedback_manage.html",
            {"feedback": feedback, "form": form, "title": self.title, "title_icon": self.title_icon},
            status=400,
        )


class FeedbackAttachmentView(LoginRequiredMixin, View):
    image_content_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }

    def get(self, request, pk):
        attachment = FeedbackAttachment.objects.select_related("feedback").filter(pk=pk).first()
        if attachment is None or not can_view_feedback(request.user, attachment.feedback):
            raise Http404
        if not attachment.file:
            raise Http404
        try:
            file_handle = attachment.file.open("rb")
        except (FileNotFoundError, OSError, ValueError) as exc:
            raise Http404 from exc

        safe_filename = sanitize_original_filename(attachment.original_filename or Path(attachment.file.name).name)
        extension = Path(attachment.file.name).suffix.lower().lstrip(".")
        is_image = extension in self.image_content_types and attachment.is_safe_image
        content_type = (
            self.image_content_types[extension]
            if is_image
            else mimetypes.guess_type(attachment.file.name)[0] or "application/octet-stream"
        )
        response = FileResponse(
            file_handle,
            as_attachment=not is_image,
            filename=safe_filename,
            content_type=content_type,
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
