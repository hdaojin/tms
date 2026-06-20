from django.urls import path

from . import views


app_name = "standards"

urlpatterns = [
    path("", views.SkillProjectListView.as_view(), name="project_list"),
    path("projects/create/", views.SkillProjectCreateView.as_view(), name="project_create"),
    path("projects/<int:pk>/", views.SkillProjectDetailView.as_view(), name="project_detail"),
    path("projects/<int:pk>/edit/", views.SkillProjectUpdateView.as_view(), name="project_edit"),
    path("domains/", views.CapabilityDomainListView.as_view(), name="domain_list"),
    path("domains/create/", views.CapabilityDomainCreateView.as_view(), name="domain_create"),
    path("domains/<int:pk>/", views.CapabilityDomainDetailView.as_view(), name="domain_detail"),
    path("domains/<int:pk>/edit/", views.CapabilityDomainUpdateView.as_view(), name="domain_edit"),
    path("skill-trees/", views.SkillTreeVersionListView.as_view(), name="tree_list"),
    path("skill-trees/create/", views.SkillTreeVersionCreateView.as_view(), name="tree_create"),
    path("skill-trees/<int:pk>/", views.SkillTreeVersionDetailView.as_view(), name="tree_detail"),
    path("skill-trees/<int:pk>/edit/", views.SkillTreeVersionUpdateView.as_view(), name="tree_edit"),
    path("nodes/", views.SkillNodeListView.as_view(), name="node_list"),
    path("nodes/create/", views.SkillNodeCreateView.as_view(), name="node_create"),
    path("nodes/<int:pk>/", views.SkillNodeDetailView.as_view(), name="node_detail"),
    path("nodes/<int:pk>/edit/", views.SkillNodeUpdateView.as_view(), name="node_edit"),
]
