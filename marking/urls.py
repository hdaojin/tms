from django.urls import path

from .views import (
    AspectSkillMapCreateView,
    AspectSkillMapDeleteView,
    MarkingResultImportView,
    MarkingSchemeDetailView,
    MarkingSchemeImportView,
    MarkingSchemeListView,
    MarkingSchemeSourceDownloadView,
)


app_name = "marking"


urlpatterns = [
    path("", MarkingSchemeListView.as_view(), name="scheme_list"),
    path("schemes/import/", MarkingSchemeImportView.as_view(), name="scheme_import"),
    path("schemes/<int:pk>/", MarkingSchemeDetailView.as_view(), name="scheme_detail"),
    path("schemes/<int:pk>/source/", MarkingSchemeSourceDownloadView.as_view(), name="scheme_source_download"),
    path("schemes/<int:scheme_pk>/results/import/", MarkingResultImportView.as_view(), name="result_import"),
    path("results/import/", MarkingResultImportView.as_view(), name="result_import_any"),
    path("aspects/<int:aspect_pk>/skill-mappings/create/", AspectSkillMapCreateView.as_view(), name="aspect_mapping_create"),
    path("skill-mappings/<int:pk>/delete/", AspectSkillMapDeleteView.as_view(), name="aspect_mapping_delete"),
]
