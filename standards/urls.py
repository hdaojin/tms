from django.urls import path

from . import views

app_name = "standards"

urlpatterns = [
    path("", views.SkillProjectListView.as_view(), name="project_list"),
    path("projects/create/", views.SkillProjectCreateView.as_view(), name="project_create"),
    path("projects/<int:pk>/", views.SkillProjectDetailView.as_view(), name="project_detail"),
    path("projects/<int:pk>/edit/", views.SkillProjectUpdateView.as_view(), name="project_edit"),
    path("catalog/", views.SkillCatalogEntryView.as_view(), name="skill_catalog_entry"),
    path("projects/<int:project_pk>/skills/", views.SkillCatalogView.as_view(), name="skill_list"),
    path(
        "projects/<int:project_pk>/domains/create/",
        views.TechnicalDomainCreateView.as_view(),
        name="domain_create",
    ),
    path(
        "projects/<int:project_pk>/domains/<int:domain_pk>/",
        views.TechnicalDomainDetailView.as_view(),
        name="domain_detail",
    ),
    path(
        "projects/<int:project_pk>/domains/<int:domain_pk>/edit/",
        views.TechnicalDomainUpdateView.as_view(),
        name="domain_edit",
    ),
    path(
        "projects/<int:project_pk>/domains/<int:domain_pk>/skills/form/reset/",
        views.skill_form_reset,
        name="skill_form_reset",
    ),
    path("skills/candidates/", views.skill_candidates, name="skill_candidates"),
    path("skills/domain-fields/", views.skill_domain_fields, name="skill_domain_fields"),
    path("skills/<int:pk>/", views.SkillDetailView.as_view(), name="skill_detail"),
    path("skills/<int:pk>/edit/", views.SkillUpdateView.as_view(), name="skill_edit"),
    path("skills/<int:pk>/aliases/", views.skill_alias_add, name="skill_alias_add"),
    path("trees/", views.SkillTreeVersionListView.as_view(), name="tree_list"),
    path("trees/create/", views.SkillTreeVersionCreateView.as_view(), name="tree_create"),
    path("trees/<int:pk>/", views.SkillTreeVersionDetailView.as_view(), name="tree_detail"),
    path("trees/<int:pk>/edit/", views.SkillTreeVersionUpdateView.as_view(), name="tree_edit"),
    path("trees/<int:tree_pk>/panel/", views.skill_tree_panel, name="tree_panel"),
    path(
        "trees/<int:tree_pk>/domains/<int:domain_pk>/quick-add/",
        views.skill_tree_quick_add,
        name="tree_quick_add_root",
    ),
    path(
        "trees/<int:tree_pk>/domains/<int:domain_pk>/candidates/",
        views.skill_tree_candidates,
        name="tree_candidates_root",
    ),
    path(
        "trees/<int:tree_pk>/domains/<int:domain_pk>/nodes/<int:parent_pk>/quick-add/",
        views.skill_tree_quick_add,
        name="tree_quick_add_child",
    ),
    path(
        "trees/<int:tree_pk>/domains/<int:domain_pk>/nodes/<int:parent_pk>/candidates/",
        views.skill_tree_candidates,
        name="tree_candidates_child",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:node_pk>/move/",
        views.skill_tree_move,
        name="tree_node_move",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:node_pk>/reorder/",
        views.skill_tree_reorder,
        name="tree_node_reorder",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:node_pk>/remove/",
        views.skill_tree_remove,
        name="tree_node_remove",
    ),
    path("wsos/", views.WSOSVersionListView.as_view(), name="wsos_list"),
    path("wsos/create/", views.WSOSVersionCreateView.as_view(), name="wsos_create"),
    path("wsos/<int:pk>/", views.WSOSVersionDetailView.as_view(), name="wsos_detail"),
    path("wsos/<int:pk>/edit/", views.WSOSVersionUpdateView.as_view(), name="wsos_edit"),
]
