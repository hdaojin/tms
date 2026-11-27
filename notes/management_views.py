from pathlib import Path

import django_tables2 as tables
from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.html import format_html
from django.views.generic import FormView
from django_tables2 import SingleTableView

from core.tables import ActionsColumn, BaseTable
from core.utils.breadcrumbs import breadcrumb_link
from core.utils.mixins import SuperuserRequiredMixin, TitleMixin

from .forms import NoteRepoForm
from .models import NoteRepo
from .paths import InvalidNotePathError, resolve_note_repo_root
from .selectors import note_repo_directory_exists, note_repo_directory_stats


def _public_status(repo):
    if not repo.allow_anonymous_access:
        return "私有", ""
    if not repo.is_visible:
        return "已隐藏，匿名访问未生效", ""
    if reason := repo.anonymous_access_block_reason():
        return reason, ""
    if not note_repo_directory_exists(repo.relative_path):
        return "目录尚未就绪，匿名链接暂不可用", ""
    return "公开", reverse("notes:note_repo_index", args=[repo.slug])


class NoteRepoManagementTable(BaseTable):
    public_access = tables.Column(verbose_name="匿名访问与链接", empty_values=(), orderable=False)
    actions = ActionsColumn(edit_url="notes:repo_manage_edit")

    class Meta(BaseTable.Meta):
        model = NoteRepo
        fields = ("title", "slug", "relative_path", "is_visible", "public_access", "actions")
        empty_text = "暂无已登记的笔记仓库"

    def render_public_access(self, record):
        status, url = _public_status(record)
        return format_html('{} <a class="link" href="{}">{}</a>', status, url, url) if url else status


class NoteRepoManagementList(SuperuserRequiredMixin, TitleMixin, SingleTableView):
    model = NoteRepo
    table_class = NoteRepoManagementTable
    template_name = "notes/repo_management_list.html"
    title = "笔记仓库管理"
    title_icon = "icon-[tabler--book]"
    table_pagination = {"per_page": 25}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repos = self.object_list.only("slug", "relative_path", "is_visible")
        context["repo_stats_rows"] = note_repo_directory_stats(repos)
        return context


class NoteRepoManagementForm(SuperuserRequiredMixin, TitleMixin, FormView):
    form_class = NoteRepoForm
    template_name = "notes/repo_management_form.html"
    title_icon = "icon-[tabler--book]"
    confirmation_salt = "notes.repo-public-confirmation"

    def get_title(self):
        return "编辑笔记仓库" if "pk" in self.kwargs else "登记笔记仓库"

    def get_breadcrumb_parents(self):
        return [breadcrumb_link("笔记仓库管理", "notes:repo_manage_list")]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.previous_public = None
        self.public_status = None
        if "pk" in self.kwargs:
            queryset = NoteRepo.objects.all()
            if self.request.method == "POST":
                queryset = queryset.select_for_update()
            repo = get_object_or_404(queryset, pk=self.kwargs["pk"])
            self.previous_public = {
                "version": repo.updated_at.isoformat(),
                "slug": repo.slug,
                "path": repo.relative_path,
                "enabled": repo.allow_anonymous_access,
                "visible": repo.is_visible,
            }
            self.public_status = _public_status(repo)
            kwargs["instance"] = repo
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["public_status"] = self.public_status
        return context

    def form_valid(self, form):
        repo = form.instance
        previous = self.previous_public
        if repo.allow_anonymous_access and (
            previous is None
            or not previous["enabled"]
            or (
                repo.is_visible
                and (not previous["visible"] or (repo.slug, repo.relative_path) != (previous["slug"], previous["path"]))
            )
        ):
            if reason := repo.anonymous_access_block_reason():
                form.add_error("relative_path", reason)
                return self.form_invalid(form)
            try:
                root = resolve_note_repo_root(repo.relative_path, require_exists=False)
                target = root.relative_to(Path(settings.NOTES_ROOT).resolve()).as_posix()
            except (InvalidNotePathError, OSError, RuntimeError, ValueError):
                form.add_error("relative_path", "无法确认公开目录的访问边界，请检查目录结构。")
                return self.form_invalid(form)
            if preview := self.public_preview(form, target):
                return self.render_to_response(self.get_context_data(form=form, preview=preview))

        try:
            with transaction.atomic():
                form.save()
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        except IntegrityError:
            form.add_error(None, "访问标识、目录或用户组已被其他操作修改，请检查后重试。")
            return self.form_invalid(form)
        messages.success(self.request, "笔记仓库已保存。")
        return redirect("notes:repo_manage_list")

    def public_preview(self, form, target):
        repo = form.instance
        payload = {
            "actor": self.request.user.pk,
            "repo": repo.pk,
            "before": self.previous_public,
            "path": repo.relative_path,
            "target": target,
            "slug": repo.slug,
            "visible": repo.is_visible,
        }
        try:
            confirmed = signing.loads(form.cleaned_data["confirmation"], salt=self.confirmation_salt, max_age=1800)
        except signing.BadSignature:
            confirmed = None
        if confirmed == payload:
            return None

        form.data = form.data.copy()
        form.data["confirmation"] = signing.dumps(payload, salt=self.confirmation_salt)
        return {
            "path": repo.relative_path,
            "target": target,
            "url": reverse("notes:note_repo_index", args=[repo.slug]),
            "visible": repo.is_visible,
        }
