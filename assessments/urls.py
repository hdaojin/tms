from django.urls import path
from . import views

app_name = "assessments"
urlpatterns = [
    path("", views.AssessmentListView.as_view(), name="assessment_list"),
    path("create/", views.AssessmentCreateView.as_view(), name="assessment_create"),
    path("people/", views.CompetitionPersonListView.as_view(), name="competition_person_list"),
    path("people/create/", views.CompetitionPersonCreateView.as_view(), name="competition_person_create"),
    path(
        "people/<int:pk>/edit/",
        views.CompetitionPersonUpdateView.as_view(),
        name="competition_person_edit",
    ),
    path("roles/", views.CompetitionRoleListView.as_view(), name="competition_role_list"),
    path("roles/create/", views.CompetitionRoleCreateView.as_view(), name="competition_role_create"),
    path(
        "roles/<int:pk>/edit/",
        views.CompetitionRoleUpdateView.as_view(),
        name="competition_role_edit",
    ),
    path("<int:pk>/", views.AssessmentDetailView.as_view(), name="assessment_detail"),
    path("<int:pk>/edit/", views.AssessmentUpdateView.as_view(), name="assessment_edit"),
    path(
        "<int:pk>/actions/<str:action>/",
        views.AssessmentLifecycleActionView.as_view(),
        name="assessment_action",
    ),
    path(
        "<int:pk>/final-results/generate/",
        views.AssessmentFinalResultsGenerateView.as_view(),
        name="final_results_generate",
    ),
    path(
        "<int:pk>/final-results/publish/",
        views.AssessmentResultsPublishView.as_view(),
        name="final_results_publish",
    ),
    path(
        "<int:pk>/awards/create/",
        views.AssessmentAwardCreateView.as_view(),
        name="award_create",
    ),
    path(
        "final-results/<int:pk>/edit/",
        views.AssessmentFinalResultUpdateView.as_view(),
        name="final_result_edit",
    ),
    path(
        "final-results/<int:pk>/confirm/",
        views.AssessmentFinalResultConfirmView.as_view(),
        name="final_result_confirm",
    ),
    path("modules/", views.AssessmentModuleListView.as_view(), name="module_list"),
    path("modules/create/", views.AssessmentModuleCreateView.as_view(), name="module_create"),
    path("modules/<int:pk>/", views.AssessmentModuleDetailView.as_view(), name="module_detail"),
    path("modules/<int:pk>/edit/", views.AssessmentModuleUpdateView.as_view(), name="module_edit"),
    path("participants/create/", views.AssessmentParticipantCreateView.as_view(), name="participant_create"),
    path("participants/<int:pk>/", views.AssessmentParticipantDetailView.as_view(), name="participant_detail"),
    path("documents/upload/", views.AssessmentDocumentCreateView.as_view(), name="document_upload"),
    path("documents/<int:pk>/download/", views.AssessmentDocumentDownloadView.as_view(), name="document_download"),
]
