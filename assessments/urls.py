from django.urls import path
from . import views

app_name = "assessments"
urlpatterns = [
    path("", views.AssessmentListView.as_view(), name="assessment_list"),
    path("create/", views.AssessmentCreateView.as_view(), name="assessment_create"),
    path("<int:pk>/", views.AssessmentDetailView.as_view(), name="assessment_detail"),
    path("<int:pk>/edit/", views.AssessmentUpdateView.as_view(), name="assessment_edit"),
    path("modules/", views.AssessmentModuleListView.as_view(), name="module_list"),
    path("modules/create/", views.AssessmentModuleCreateView.as_view(), name="module_create"),
    path("modules/<int:pk>/", views.AssessmentModuleDetailView.as_view(), name="module_detail"),
    path("modules/<int:pk>/edit/", views.AssessmentModuleUpdateView.as_view(), name="module_edit"),
    path("participants/create/", views.AssessmentParticipantCreateView.as_view(), name="participant_create"),
    path("participants/<int:pk>/", views.AssessmentParticipantDetailView.as_view(), name="participant_detail"),
    path("documents/upload/", views.AssessmentDocumentCreateView.as_view(), name="document_upload"),
    path("documents/<int:pk>/download/", views.AssessmentDocumentDownloadView.as_view(), name="document_download"),
]
