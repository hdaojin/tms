from django.urls import path

from . import views


app_name = "glossary"

urlpatterns = [
    path("", views.GlossaryBrowseView.as_view(), name="browse"),
    path("study/", views.StudyStartView.as_view(), name="study_start"),
    path("study/<int:pk>/", views.StudySessionView.as_view(), name="study_session"),
    path("study/<int:pk>/answer/", views.StudyAnswerView.as_view(), name="study_answer"),
    path("study/<int:pk>/stop/", views.StudyStopView.as_view(), name="study_stop"),
    path("study/<int:pk>/summary/", views.StudySessionSummaryView.as_view(), name="session_summary"),
    path("stats/", views.MyStatisticsView.as_view(), name="my_stats"),
    path("manage/stats/", views.AllStatisticsView.as_view(), name="all_stats"),
    path("proposals/", views.ProposalListView.as_view(), name="proposal_list"),
    path("proposals/create/", views.ProposalCreateView.as_view(), name="proposal_create"),
    path("proposals/<int:pk>/", views.ProposalDetailView.as_view(), name="proposal_detail"),
    path("proposals/<int:pk>/edit/", views.ProposalUpdateView.as_view(), name="proposal_edit"),
    path("proposals/<int:pk>/approve/", views.ProposalApproveView.as_view(), name="proposal_approve"),
    path("proposals/<int:pk>/reject/", views.ProposalRejectView.as_view(), name="proposal_reject"),
    path("manage/glossaries/", views.ProfessionalGlossaryListView.as_view(), name="glossary_list"),
    path("manage/glossaries/create/", views.ProfessionalGlossaryCreateView.as_view(), name="glossary_create"),
    path("manage/glossaries/<int:pk>/edit/", views.ProfessionalGlossaryUpdateView.as_view(), name="glossary_edit"),
    path("manage/glossaries/<int:glossary_pk>/entries/", views.GlossaryEntryListView.as_view(), name="manage_entry_list"),
    path("manage/entries/create/", views.GlossaryEntryCreateView.as_view(), name="entry_create"),
    path("manage/entries/<int:pk>/edit/", views.GlossaryEntryUpdateView.as_view(), name="entry_edit"),
    path("manage/imports/", views.GlossaryImportListView.as_view(), name="import_list"),
    path("manage/imports/create/", views.GlossaryImportCreateView.as_view(), name="import_create"),
    path("manage/imports/<int:pk>/preview/", views.GlossaryImportPreviewView.as_view(), name="import_preview"),
    path("manage/imports/<int:pk>/", views.GlossaryImportDetailView.as_view(), name="import_detail"),
    path("manage/imports/<int:pk>/download/", views.GlossaryImportDownloadView.as_view(), name="import_download"),
]
