from django.urls import path

from . import views


app_name = "examcontent"

urlpatterns = [
    path("", views.ExamPaperListView.as_view(), name="paper_list"),
    path("papers/create/", views.ExamPaperCreateView.as_view(), name="paper_create"),
    path("papers/<int:pk>/", views.ExamPaperDetailView.as_view(), name="paper_detail"),
    path("papers/<int:pk>/edit/", views.ExamPaperUpdateView.as_view(), name="paper_edit"),
    path("requirements/", views.ExamRequirementListView.as_view(), name="requirement_list"),
    path("requirements/create/", views.ExamRequirementCreateView.as_view(), name="requirement_create"),
    path("requirements/<int:pk>/", views.ExamRequirementDetailView.as_view(), name="requirement_detail"),
    path("requirements/<int:pk>/edit/", views.ExamRequirementUpdateView.as_view(), name="requirement_edit"),
]
