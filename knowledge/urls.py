from django.urls import path

from . import views


app_name = "knowledge"

urlpatterns = [
    path("", views.KnowledgeEvidenceListView.as_view(), name="evidence_list"),
    path("unmapped/", views.UnmappedEvidenceListView.as_view(), name="unmapped"),
    path("evidences/create/", views.KnowledgeEvidenceCreateView.as_view(), name="evidence_create"),
    path("evidences/<int:pk>/", views.KnowledgeEvidenceDetailView.as_view(), name="evidence_detail"),
    path("evidences/<int:pk>/edit/", views.KnowledgeEvidenceUpdateView.as_view(), name="evidence_edit"),
    path("evidences/<int:pk>/approve/", views.KnowledgeEvidenceApproveView.as_view(), name="evidence_approve"),
    path("evidences/<int:pk>/reject/", views.KnowledgeEvidenceRejectView.as_view(), name="evidence_reject"),
    path("mappings/create/", views.KnowledgeEvidenceSkillMapCreateView.as_view(), name="mapping_create"),
    path("mappings/<int:pk>/delete/", views.KnowledgeEvidenceSkillMapDeleteView.as_view(), name="mapping_delete"),
]
