from django.urls import path

from . import views


app_name = "archives"

urlpatterns = [
    path("", views.ArchiveAssetListView.as_view(), name="asset_list"),
    path("upload/", views.ArchiveAssetCreateView.as_view(), name="asset_upload"),
    path("<int:pk>/", views.ArchiveAssetDetailView.as_view(), name="asset_detail"),
    path("<int:pk>/edit/", views.ArchiveAssetUpdateView.as_view(), name="asset_edit"),
    path("<int:pk>/download/", views.ArchiveAssetDownloadView.as_view(), name="asset_download"),
]
