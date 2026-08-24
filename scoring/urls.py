from django.urls import path

from . import views


app_name = "scoring"

urlpatterns = [
    path("", views.ScoringSchemeListView.as_view(), name="scheme_list"),
    path("import/", views.ScoringImportView.as_view(), name="scheme_import"),
    path("imports/<int:pk>/preview/", views.ScoringSchemeImportPreviewView.as_view(), name="scheme_import_preview"),
    path(
        "parsers/<str:parser_key>/template/", views.ScoringParserTemplateDownloadView.as_view(), name="parser_template"
    ),
    path("schemes/<int:pk>/", views.ScoringSchemeDetailView.as_view(), name="scheme_detail"),
    path("modules/<int:module_pk>/online/", views.OnlineScoringWorkspaceView.as_view(), name="online_scoring"),
    path(
        "modules/<int:module_pk>/online/participants/<int:participant_pk>/aspects/<int:aspect_pk>/",
        views.OnlineScoringEntryView.as_view(),
        name="online_scoring_entry",
    ),
    path("results/create/", views.ScoringResultCreateView.as_view(), name="result_create"),
]
