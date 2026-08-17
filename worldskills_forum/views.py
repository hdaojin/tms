from __future__ import annotations

import mimetypes

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from core.utils.listing import FilterableListMixin, ListFilterSpec
from core.utils.mixins import TitleMixin

from .forms import AttachmentAddForm, AttachmentMetadataFormSet, ForumPostTranslationForm, ForumTopicForm
from .models import ForumCategory, ForumModule, ForumPost, ForumPostAttachment, ForumTag, ForumTopic, Importance, PostType, TopicStatus
from .permissions import OwnerOrChangePermissionMixin, can_edit_post, can_edit_topic
from .selectors import get_published_post_feed, get_topic_list_queryset, get_topic_timeline, topic_queryset_base
from .services import add_post_attachments, create_published_post, mark_topic_viewed, update_published_post


FILTER_KEYS = ("q", "year", "module", "category", "tag", "post_type", "importance", "view")


def _filter_context(request):
    return {
        "filters": {key: request.GET.get(key, "") for key in FILTER_KEYS},
        "years": ForumTopic.objects.filter(posts__translation__isnull=False).values_list("competition_year", flat=True).distinct().order_by("-competition_year"),
        "modules": ForumModule.objects.filter(is_active=True),
        "categories": ForumCategory.objects.filter(is_active=True),
        "tags": ForumTag.objects.all(),
        "post_types": PostType.choices,
        "importance_choices": Importance.choices,
    }


def _visible_topic_queryset(user):
    queryset = topic_queryset_base()
    if user.has_perm("worldskills_forum.change_all_forum_content"):
        return queryset
    return queryset.filter(Q(posts__translation__isnull=False) | Q(created_by=user)).distinct()


class ForumFeedView(TitleMixin, PermissionRequiredMixin, ListView):
    template_name = "worldskills_forum/feed.html"
    context_object_name = "posts"
    paginate_by = 20
    title = "世赛论坛最新动态"
    title_icon = "icon-[tabler--messages]"
    permission_required = "worldskills_forum.view_forumpost"

    def get_queryset(self):
        return get_published_post_feed(self.request.user, self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_filter_context(self.request))
        return context


class FilterShortcutView(PermissionRequiredMixin, View):
    filter_name = "all"
    permission_required = "worldskills_forum.view_forumpost"

    def get(self, request):
        return redirect(f"{reverse('worldskills_forum:feed')}?view={self.filter_name}")


class ImportantFeedView(FilterShortcutView):
    filter_name = "important"


class OfficialFeedView(FilterShortcutView):
    filter_name = "official"


class UnreadFeedView(FilterShortcutView):
    filter_name = "unread"


class ForumTopicListView(TitleMixin, PermissionRequiredMixin, FilterableListMixin, ListView):
    template_name = "worldskills_forum/topic_list.html"
    context_object_name = "topics"
    paginate_by = 20
    title = "论坛主题"
    title_icon = "icon-[tabler--message-circle]"
    permission_required = "worldskills_forum.view_forumtopic"

    search_fields = (
        "translated_title",
        "original_title",
        "summary",
        "module__name",
        "tags__name",
        "category__name",
        "posts__author_name",
        "posts__original_content",
        "posts__translation__translated_content",
        "posts__attachments__original_filename",
        "posts__attachments__caption_zh",
    )
    search_requires_distinct = True
    always_distinct = True
    list_filter_target_id = "forum-topic-list"

    def get_list_filter_specs(self):
        years = (
            ForumTopic.objects.filter(posts__translation__isnull=False)
            .values_list("competition_year", flat=True)
            .distinct()
            .order_by("-competition_year")
        )
        modules = ForumModule.objects.filter(is_active=True).values_list("pk", "name")
        categories = ForumCategory.objects.filter(is_active=True).values_list("pk", "name")
        tags = ForumTag.objects.values_list("pk", "name")
        return (
            ListFilterSpec(
                name="year",
                label="年份",
                control="select",
                lookup="competition_year",
                choices=tuple((year, year) for year in years),
                empty_label="全部年份",
            ),
            ListFilterSpec(
                name="module",
                label="模块",
                control="select",
                lookup="module_id",
                choices=tuple(modules),
                empty_label="全部模块",
            ),
            ListFilterSpec(
                name="category",
                label="分类",
                control="select",
                lookup="category_id",
                choices=tuple(categories),
                empty_label="全部分类",
            ),
            ListFilterSpec(
                name="tag",
                label="标签",
                control="select",
                lookup="tags__id",
                choices=tuple(tags),
                empty_label="全部标签",
            ),
            ListFilterSpec(
                name="post_type",
                label="信息类型",
                control="select",
                lookup="posts__post_type",
                choices=PostType.choices,
                empty_label="全部类型",
            ),
            ListFilterSpec(
                name="status",
                label="状态",
                control="select",
                lookup="status",
                choices=TopicStatus.choices,
                empty_label="全部状态",
            ),
            ListFilterSpec(
                name="importance",
                label="重要程度",
                control="select",
                lookup="importance",
                choices=Importance.choices,
                empty_label="全部程度",
            ),
            ListFilterSpec(
                name="q",
                label="搜索",
                control="search",
                placeholder="搜索中英文、作者、标签和附件名称",
            ),
        )

    def get_base_queryset(self):
        queryset = get_topic_list_queryset()
        if not self.request.user.has_perm("worldskills_forum.change_all_forum_content"):
            queryset = queryset.filter(Q(post_count__gt=0) | Q(created_by=self.request.user))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_create"] = self.request.user.has_perm("worldskills_forum.add_forumtopic")
        return context


class ForumTopicDetailView(TitleMixin, PermissionRequiredMixin, DetailView):
    template_name = "worldskills_forum/topic_detail.html"
    context_object_name = "topic"
    title = "{translated_title}"
    title_icon = "icon-[tabler--message-circle]"
    permission_required = "worldskills_forum.view_forumtopic"

    def get_queryset(self):
        return _visible_topic_queryset(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        posts = list(get_topic_timeline(self.object))
        state = self.object.read_states.filter(user=self.request.user).first()
        if state:
            old_posts = [post for post in posts if post.translation.published_at <= state.last_viewed_at]
            new_posts = [post for post in posts if post.translation.published_at > state.last_viewed_at]
        else:
            old_posts, new_posts = posts, []
        context.update(
            {
                "old_posts": old_posts,
                "new_posts": new_posts,
                "show_unread_divider": bool(state and new_posts),
                "can_edit_topic": can_edit_topic(self.request.user, self.object),
                "can_delete_empty_topic": not posts and (self.object.created_by_id == self.request.user.pk or self.request.user.has_perm("worldskills_forum.delete_forumtopic") or self.request.user.is_superuser),
                "can_add_post": self.request.user.has_perms(["worldskills_forum.add_forumpost", "worldskills_forum.add_forumtranslation"]),
            }
        )
        for post in posts:
            post.can_edit = can_edit_post(self.request.user, post)
        mark_topic_viewed(self.request.user, self.object, timezone.now())
        return context


class ForumTopicCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ForumTopic
    form_class = ForumTopicForm
    template_name = "worldskills_forum/form.html"
    permission_required = "worldskills_forum.add_forumtopic"
    raise_exception = True
    title = "创建论坛主题"
    title_icon = "icon-[tabler--message-plus]"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "论坛主题已创建，请继续发布首条翻译。")
        return response

    def get_success_url(self):
        return reverse("worldskills_forum:post_create", kwargs={"topic_pk": self.object.pk})


class ForumTopicUpdateView(OwnerOrChangePermissionMixin, TitleMixin, LoginRequiredMixin, UpdateView):
    model = ForumTopic
    form_class = ForumTopicForm
    template_name = "worldskills_forum/form.html"
    permission_name = "worldskills_forum.change_forumtopic"
    title = "编辑论坛主题"
    title_icon = "icon-[tabler--edit]"

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, "论坛主题已更新。")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("worldskills_forum:topic_detail", kwargs={"pk": self.object.pk})


class ForumTopicDeleteView(TitleMixin, PermissionRequiredMixin, DeleteView):
    model = ForumTopic
    template_name = "worldskills_forum/confirm_delete.html"
    success_url = reverse_lazy("worldskills_forum:topic_list")
    title = "删除论坛主题"
    title_icon = "icon-[tabler--trash]"
    permission_required = "worldskills_forum.delete_forumtopic"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        is_empty_owner = obj.created_by_id == self.request.user.pk and not obj.posts.exists()
        if self.request.user.has_perm("worldskills_forum.change_all_forum_content") or is_empty_owner:
            return obj
        raise Http404

    def form_valid(self, form):
        messages.success(self.request, "论坛主题已删除。")
        return super().form_valid(form)


class ForumPostTranslationCreateView(TitleMixin, PermissionRequiredMixin, FormView):
    form_class = ForumPostTranslationForm
    template_name = "worldskills_forum/post_form.html"
    permission_required = ("worldskills_forum.add_forumpost", "worldskills_forum.add_forumtranslation")
    raise_exception = True
    title = "发布论坛翻译"
    title_icon = "icon-[tabler--language]"

    def dispatch(self, request, *args, **kwargs):
        self.topic = get_object_or_404(_visible_topic_queryset(request.user), pk=kwargs["topic_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "topic": self.topic}

    def get_context_data(self, **kwargs):
        return super().get_context_data(topic=self.topic, glossary_url=reverse("glossary:browse"), **kwargs)

    def form_valid(self, form):
        post = create_published_post(
            topic=self.topic, post_data=form.post_data(), translation_data=form.translation_data(), user=self.request.user,
            uploaded_attachments=form.cleaned_data["attachments"], external_attachment_urls=form.cleaned_data["external_attachment_urls"],
        )
        messages.success(self.request, "论坛翻译信息已发布。")
        return redirect("worldskills_forum:topic_detail", pk=post.topic_id)


class ForumPostTranslationUpdateView(TitleMixin, LoginRequiredMixin, FormView):
    form_class = ForumPostTranslationForm
    template_name = "worldskills_forum/post_form.html"
    title = "编辑已发布翻译"
    title_icon = "icon-[tabler--edit]"

    def dispatch(self, request, *args, **kwargs):
        self.forum_post = get_object_or_404(ForumPost.objects.select_related("topic", "translation"), pk=kwargs["pk"])
        if not can_edit_post(request.user, self.forum_post):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "post": self.forum_post, "include_attachments": False}

    def get_context_data(self, **kwargs):
        return super().get_context_data(topic=self.forum_post.topic, post=self.forum_post, glossary_url=reverse("glossary:browse"), **kwargs)

    def form_valid(self, form):
        update_published_post(post=self.forum_post, post_data=form.post_data(), translation_data=form.translation_data(), user=self.request.user)
        messages.success(self.request, "论坛翻译信息已更新。")
        return redirect("worldskills_forum:topic_detail", pk=self.forum_post.topic_id)


class ForumPostDeleteView(TitleMixin, PermissionRequiredMixin, DeleteView):
    model = ForumPost
    permission_required = "worldskills_forum.delete_forumpost"
    raise_exception = True
    template_name = "worldskills_forum/confirm_delete.html"
    title = "删除论坛帖子"
    title_icon = "icon-[tabler--trash]"

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.has_perm("worldskills_forum.change_all_forum_content"):
            return queryset
        return queryset.filter(created_by=self.request.user)

    def get_success_url(self):
        return reverse("worldskills_forum:topic_detail", kwargs={"pk": self.object.topic_id})


class ForumPostAttachmentManageView(TitleMixin, PermissionRequiredMixin, TemplateView):
    template_name = "worldskills_forum/attachment_manage.html"
    title = "管理论坛附件"
    title_icon = "icon-[tabler--paperclip]"
    permission_required = "worldskills_forum.change_forumpostattachment"

    def dispatch(self, request, *args, **kwargs):
        self.forum_post = get_object_or_404(ForumPost.objects.select_related("topic", "translation"), pk=kwargs["post_pk"])
        if not can_edit_post(request.user, self.forum_post):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def _forms(self, data=None, files=None):
        queryset = self.forum_post.attachments.all()
        return AttachmentAddForm(data, files, post=self.forum_post, prefix="add"), AttachmentMetadataFormSet(data, queryset=queryset, prefix="meta")

    def get_context_data(self, **kwargs):
        if "add_form" not in kwargs or "metadata_formset" not in kwargs:
            add_form, metadata_formset = self._forms()
            kwargs.setdefault("add_form", add_form)
            kwargs.setdefault("metadata_formset", metadata_formset)
        return super().get_context_data(post=self.forum_post, **kwargs)

    def post(self, request, *args, **kwargs):
        add_form, metadata_formset = self._forms(request.POST, request.FILES)
        action = request.POST.get("action")
        if action == "add" and add_form.is_valid():
            add_post_attachments(post=self.forum_post, user=request.user, uploaded_attachments=add_form.cleaned_data["attachments"], external_attachment_urls=add_form.cleaned_data["external_attachment_urls"])
            messages.success(request, "附件已添加。")
            return redirect("worldskills_forum:attachment_manage", post_pk=self.forum_post.pk)
        if action == "metadata" and metadata_formset.is_valid():
            metadata_formset.save()
            messages.success(request, "附件信息已更新。")
            return redirect("worldskills_forum:attachment_manage", post_pk=self.forum_post.pk)
        return self.render_to_response(self.get_context_data(add_form=add_form, metadata_formset=metadata_formset))


class ForumAttachmentDeleteView(TitleMixin, PermissionRequiredMixin, DeleteView):
    model = ForumPostAttachment
    template_name = "worldskills_forum/confirm_delete.html"
    title = "删除论坛附件"
    title_icon = "icon-[tabler--trash]"
    permission_required = "worldskills_forum.delete_forumpostattachment"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset.select_related("post__translation") if queryset is not None else ForumPostAttachment.objects.select_related("post__translation"))
        if not can_edit_post(self.request.user, obj.post):
            raise Http404
        return obj

    def get_success_url(self):
        return reverse("worldskills_forum:attachment_manage", kwargs={"post_pk": self.object.post_id})


class ForumAttachmentContentView(PermissionRequiredMixin, View):
    permission_required = "worldskills_forum.view_forumpostattachment"

    def get(self, request, pk):
        attachment = get_object_or_404(
            ForumPostAttachment.objects.select_related("post__topic").filter(
                post__topic__in=_visible_topic_queryset(request.user)
            ),
            pk=pk,
            file__isnull=False,
        )
        if not attachment.file or not attachment.post_id:
            raise Http404
        try:
            file_handle = attachment.file.open("rb")
        except (FileNotFoundError, OSError, ValueError) as exc:
            raise Http404 from exc
        content_type = mimetypes.guess_type(attachment.file.name)[0] or "application/octet-stream"
        response = FileResponse(file_handle, as_attachment=not attachment.is_safe_image, filename=attachment.original_filename, content_type=content_type)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class ForumTranslationWorkbenchView(TitleMixin, LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "worldskills_forum/workbench.html"
    title = "论坛翻译工作台"
    title_icon = "icon-[tabler--language]"
    raise_exception = True

    def test_func(self):
        return self.request.user.has_perm("worldskills_forum.add_forumtopic") or self.request.user.has_perm("worldskills_forum.add_forumpost")

    def get_context_data(self, **kwargs):
        active_topics = get_topic_list_queryset().filter(post_count__gt=0)[:10]
        empty_topics = ForumTopic.objects.filter(created_by=self.request.user, posts__isnull=True).select_related("category", "module")
        recent = ForumPost.objects.filter(translation__translated_by=self.request.user).select_related("topic", "translation").order_by("-translation__updated_at")[:10]
        return super().get_context_data(active_topics=active_topics, empty_topics=empty_topics, recent_posts=recent, can_create_topic=self.request.user.has_perm("worldskills_forum.add_forumtopic"), can_publish=self.request.user.has_perms(["worldskills_forum.add_forumpost", "worldskills_forum.add_forumtranslation"]), **kwargs)
