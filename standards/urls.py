from django.urls import path

from . import views

app_name = "standards"

urlpatterns = [
    path("", views.SkillProjectListView.as_view(), name="project_list"),
    path("projects/", views.CurrentSkillTreeEntryView.as_view(), name="current_tree_entry"),
    path("projects/create/", views.SkillProjectCreateView.as_view(), name="project_create"),
    path("projects/<int:pk>/", views.SkillProjectDetailView.as_view(), name="project_detail"),
    path("projects/<int:pk>/edit/", views.SkillProjectUpdateView.as_view(), name="project_edit"),
    path(
        "projects/<int:project_pk>/domains/create/",
        views.TechnicalDomainCreateView.as_view(),
        name="domain_create",
    ),
    path(
        "projects/<int:project_pk>/domains/<int:domain_pk>/tree/",
        views.CurrentDomainSkillTreeView.as_view(),
        name="current_domain_tree",
    ),
    path(
        "projects/<int:project_pk>/domains/<int:domain_pk>/tree/list/",
        views.SkillTreeNodeListView.as_view(),
        name="current_domain_tree_list",
    ),
    path(
        "projects/<int:project_pk>/domains/<int:domain_pk>/trees/create/",
        views.SkillTreeVersionCreateView.as_view(),
        name="domain_tree_create",
    ),
    path(
        "projects/<int:project_pk>/domains/<int:domain_pk>/edit/",
        views.TechnicalDomainUpdateView.as_view(),
        name="domain_edit",
    ),
    path("skills/candidates/", views.skill_candidates, name="skill_candidates"),
    path("skills/domain-fields/", views.skill_domain_fields, name="skill_domain_fields"),
    path("skills/<int:pk>/", views.SkillDetailView.as_view(), name="skill_detail"),
    path("skills/<int:pk>/edit/", views.SkillUpdateView.as_view(), name="skill_edit"),
    path("skills/<int:pk>/aliases/", views.skill_alias_add, name="skill_alias_add"),
    path("trees/", views.SkillTreeVersionListView.as_view(), name="tree_list"),
    path("trees/<int:pk>/", views.SkillTreeVersionDetailView.as_view(), name="tree_detail"),
    path("trees/<int:tree_pk>/list/", views.SkillTreeNodeListView.as_view(), name="tree_node_list"),
    path("trees/<int:pk>/edit/", views.SkillTreeVersionUpdateView.as_view(), name="tree_edit"),
    path("trees/<int:tree_pk>/set-current/", views.skill_tree_set_current, name="tree_set_current"),
    path(
        "trees/<int:tree_pk>/panel/",
        views.skill_tree_panel,
        name="tree_panel",
    ),
    path(
        "trees/<int:tree_pk>/search/",
        views.skill_tree_search,
        name="tree_search",
    ),
    path(
        "trees/<int:tree_pk>/unmounted-skills/",
        views.skill_tree_unmounted_skills,
        name="tree_unmounted_skills",
    ),
    path(
        "trees/<int:tree_pk>/skills/<int:skill_pk>/attach/",
        views.skill_tree_attach_existing,
        name="tree_attach_existing_skill",
    ),
    path(
        "trees/<int:tree_pk>/quick-add/",
        views.skill_tree_quick_add,
        name="tree_quick_add_root",
    ),
    path(
        "trees/<int:tree_pk>/candidates/",
        views.skill_tree_candidates,
        name="tree_candidates_root",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:parent_pk>/quick-add/",
        views.skill_tree_quick_add,
        name="tree_quick_add_child",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:parent_pk>/candidates/",
        views.skill_tree_candidates,
        name="tree_candidates_child",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:node_pk>/quick-add-sibling/",
        views.skill_tree_quick_add_sibling,
        name="tree_quick_add_sibling",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:node_pk>/candidates-sibling/",
        views.skill_tree_candidates_sibling,
        name="tree_candidates_sibling",
    ),
    path(
        "trees/<int:tree_pk>/skill-create/",
        views.skill_tree_detailed_create_root,
        name="tree_skill_create_root",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:parent_pk>/skill-create-child/",
        views.skill_tree_detailed_create_child,
        name="tree_skill_create_child",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:node_pk>/skill-create-sibling/",
        views.skill_tree_detailed_create_sibling,
        name="tree_skill_create_sibling",
    ),
    path(
        "trees/<int:tree_pk>/nodes/<int:node_pk>/skill-edit/",
        views.skill_tree_skill_edit,
        name="tree_node_skill_edit",
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
    path("wsos/<int:wsos_pk>/sections/create/", views.WSOSSectionCreateView.as_view(), name="wsos_section_create"),
    path("wsos/sections/<int:pk>/edit/", views.WSOSSectionUpdateView.as_view(), name="wsos_section_edit"),
    path("wsos/sections/<int:section_pk>/delete/", views.wsos_section_delete, name="wsos_section_delete"),
    path(
        "wsos/sections/<int:section_pk>/skill-candidates/",
        views.wsos_section_skill_candidates,
        name="wsos_section_skill_candidates",
    ),
    path(
        "wsos/sections/<int:section_pk>/skills/<int:skill_pk>/map/",
        views.wsos_section_map_skill,
        name="wsos_section_map_skill",
    ),
    path("wsos/mappings/<int:mapping_pk>/edit/", views.wsos_mapping_note_edit, name="wsos_mapping_edit"),
    path("wsos/mappings/<int:mapping_pk>/delete/", views.wsos_mapping_delete, name="wsos_mapping_delete"),
]
