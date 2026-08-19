from django.urls import path
from . import views

app_name = "evidence"
urlpatterns = [
    path("", views.KnowledgeEvidenceListView.as_view(), name="evidence_list"),
    path("create/", views.KnowledgeEvidenceCreateView.as_view(), name="evidence_create"),
    path("<int:pk>/", views.KnowledgeEvidenceDetailView.as_view(), name="evidence_detail"),
    path("<int:pk>/edit/", views.KnowledgeEvidenceUpdateView.as_view(), name="evidence_edit"),
    path("<int:pk>/approve/", views.KnowledgeEvidenceApproveView.as_view(), name="evidence_approve"),
    path("<int:pk>/reject/", views.KnowledgeEvidenceRejectView.as_view(), name="evidence_reject"),
    path("<int:evidence_pk>/mappings/create/", views.EvidenceSkillMapCreateView.as_view(), name="mapping_create"),
    path("mappings/<int:pk>/delete/", views.EvidenceSkillMapDeleteView.as_view(), name="mapping_delete"),
]
