from django.urls import path

from .views import (
    SkillNodeCreateView,
    SkillNodeDeactivateView,
    SkillNodeInlineCreateView,
    SkillNodeUpdateView,
    SkillTreeCreateView,
    SkillTreeDetailView,
    SkillTreeListView,
)


app_name = "skilltrees"


urlpatterns = [
    path("", SkillTreeListView.as_view(), name="list"),
    path("create/", SkillTreeCreateView.as_view(), name="create"),
    path("<int:pk>/", SkillTreeDetailView.as_view(), name="detail"),
    path("<int:tree_pk>/nodes/create/", SkillNodeCreateView.as_view(), name="node_create"),
    path("<int:tree_pk>/nodes/quick-create/", SkillNodeInlineCreateView.as_view(), name="node_quick_create"),
    path("nodes/<int:pk>/edit/", SkillNodeUpdateView.as_view(), name="node_edit"),
    path("nodes/<int:pk>/deactivate/", SkillNodeDeactivateView.as_view(), name="node_deactivate"),
]
