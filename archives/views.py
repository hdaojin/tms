from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import FileResponse, Http404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, UpdateView
from django_tables2 import SingleTableView

from core.utils.mixins import TitleMixin

from .forms import ArchiveAssetForm
from .models import ArchiveAsset
from .tables import ArchiveAssetTable


class ArchiveAssetListView(TitleMixin, LoginRequiredMixin, SingleTableView):
    model = ArchiveAsset
    table_class = ArchiveAssetTable
    template_name = "archives/asset_list.html"
    title = "资料资产"
    title_icon = "icon-[tabler--archive]"

    def get_queryset(self):
        return super().get_queryset().select_related("skill_project", "uploaded_by", "target_content_type")


class ArchiveAssetDetailView(TitleMixin, LoginRequiredMixin, DetailView):
    model = ArchiveAsset
    template_name = "archives/asset_detail.html"
    context_object_name = "asset"
    title = "{title}"
    title_icon = "icon-[tabler--archive]"


class ArchiveAssetCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    model = ArchiveAsset
    form_class = ArchiveAssetForm
    template_name = "common/form.html"
    permission_required = "archives.add_archiveasset"
    title = "上传资料资产"
    title_icon = "icon-[tabler--upload]"

    def form_valid(self, form):
        if form.instance.uploaded_by_id is None:
            form.instance.uploaded_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("archives:asset_detail", args=[self.object.pk])


class ArchiveAssetUpdateView(TitleMixin, PermissionRequiredMixin, UpdateView):
    model = ArchiveAsset
    form_class = ArchiveAssetForm
    template_name = "common/form.html"
    permission_required = "archives.change_archiveasset"
    title = "编辑资料资产"
    title_icon = "icon-[tabler--edit]"

    def get_success_url(self):
        return reverse("archives:asset_detail", args=[self.object.pk])


class ArchiveAssetDownloadView(LoginRequiredMixin, DetailView):
    model = ArchiveAsset

    def get(self, request, *args, **kwargs):
        asset = self.get_object()
        if not asset.file:
            raise Http404
        return FileResponse(asset.file.open("rb"), as_attachment=True, filename=asset.filename)

# Create your views here.
