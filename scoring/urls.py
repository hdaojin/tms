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
    path("participants/create/", views.ScoringParticipantCreateView.as_view(), name="participant_create"),
    path("participants/<int:pk>/", views.ScoringParticipantDetailView.as_view(), name="participant_detail"),
    path("participants/<int:pk>/edit/", views.ScoringParticipantUpdateView.as_view(), name="participant_edit"),
    path("results/create/", views.ScoringResultCreateView.as_view(), name="result_create"),
]
