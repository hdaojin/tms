from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, UpdateView, DeleteView, View
from django_tables2 import SingleTableView

from core.file_preview import build_download_response
from core.utils.breadcrumbs import breadcrumb_link
from core.utils.mixins import TitleMixin
from .forms import TrainingLogTemplateForm
from .log_templates import downloadable_log_templates, save_log_template, delete_log_template
from .models import TrainingLogTemplate
from .tables import TrainingLogTemplateTable


class TemplatePageMixin(TitleMixin, PermissionRequiredMixin):
    model = TrainingLogTemplate
    title_icon = "icon-[tabler--file-text]"

    def get_breadcrumb_parents(self):
        return [breadcrumb_link("训练日志模板", "training:log_template_list")]


class LogTemplateListView(TemplatePageMixin, SingleTableView):
    table_class = TrainingLogTemplateTable
    template_name = "training/object_list.html"
    title = "训练日志模板"
    permission_required = "training.view_traininglogtemplate"
    table_pagination = {"per_page": 25}

    def get_breadcrumb_parents(self):
        return []

    def get_queryset(self):
        return TrainingLogTemplate.objects.select_related("training_cycle")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(create_label="上传日志模板", create_url_name=(
            "training:log_template_create" if self.request.user.has_perm("training.add_traininglogtemplate") else None
        ))
        return context


class LogTemplateCreateView(TemplatePageMixin, CreateView):
    form_class = TrainingLogTemplateForm
    template_name = "common/form.html"
    title = "上传训练日志模板"
    permission_required = ("training.view_traininglogtemplate", "training.add_traininglogtemplate")
    success_url = reverse_lazy("training:log_template_list")

    def form_valid(self, form):
        try:
            self.object = save_log_template(form.save(commit=False), actor=self.request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        from django.http import HttpResponseRedirect

        messages.success(self.request, "日志模板已保存。")
        return HttpResponseRedirect(self.get_success_url())


class LogTemplateUpdateView(LogTemplateCreateView, UpdateView):
    title = "修改训练日志模板"
    permission_required = ("training.view_traininglogtemplate", "training.change_traininglogtemplate")


class LogTemplateDeleteView(TemplatePageMixin, DeleteView):
    title = "删除训练日志模板"
    template_name = "training/log_template_confirm_delete.html"
    permission_required = ("training.view_traininglogtemplate", "training.delete_traininglogtemplate")
    success_url = reverse_lazy("training:log_template_list")

    def form_valid(self, form):
        from django.http import HttpResponseRedirect

        delete_log_template(self.object, actor=self.request.user)
        messages.success(self.request, "日志模板及其文件已删除。")
        return HttpResponseRedirect(self.get_success_url())


class LogTemplateDownloadView(View):
    def get(self, request, pk):
        if request.user.has_perm("training.view_traininglogtemplate"):
            templates = TrainingLogTemplate.objects.all()
        else:
            templates = downloadable_log_templates(request.user, backfill=request.GET.get("backfill") == "1")
        template = get_object_or_404(templates, pk=pk)
        return build_download_response(template.file, Path(template.file.name).name)


def log_template_context(user, cycle_id, *, backfill=False):
    # 无效的选择不能扩大成全部模板。
    cycle_id = str(cycle_id or "")
    templates = downloadable_log_templates(user, backfill=backfill)
    valid_id = cycle_id.isdecimal() and len(cycle_id) <= 19 and int(cycle_id) <= 2**63 - 1
    templates = templates.filter(training_cycle_id=int(cycle_id)) if valid_id else templates.none()
    return {"log_templates": templates, "template_cycle_selected": bool(cycle_id), "template_backfill": backfill}


@require_GET
@permission_required("training.add_traininglog", raise_exception=True)
def log_template_links(request):
    return render(request, "training/_log_template_links.html", log_template_context(
        request.user, request.GET.get("training_cycle"), backfill=True,
    ))


def configure_log_template_form(form, *, backfill):
    if backfill:
        form.fields["training_cycle"].widget.attrs.update({
            "hx-get": reverse("training:log_template_links"),
            "hx-trigger": "change, reset from:closest form delay:1ms",
            "hx-target": "#log-template-downloads", "hx-swap": "outerHTML",
            "hx-include": "this", "hx-sync": "this:replace",
        })
