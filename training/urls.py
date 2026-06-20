from django.urls import path

from . import views


app_name = "training"

urlpatterns = [
    path("", views.TrainingCycleListView.as_view(), name="cycle_list"),
    path("cycles/create/", views.TrainingCycleCreateView.as_view(), name="cycle_create"),
    path("cycles/<int:pk>/", views.TrainingCycleDetailView.as_view(), name="cycle_detail"),
    path("cycles/<int:pk>/edit/", views.TrainingCycleUpdateView.as_view(), name="cycle_edit"),
    path("logs/", views.TrainingLogListView.as_view(), name="log_list"),
    path("logs/upload/", views.TrainingLogCreateView.as_view(), name="log_upload"),
    path("logs/<int:pk>/", views.TrainingLogDetailView.as_view(), name="log_detail"),
    path("logs/<int:pk>/edit/", views.TrainingLogUpdateView.as_view(), name="log_edit"),
    path("logs/monthly-stats/", views.TrainingLogMonthlyStatView.as_view(), name="monthly_stats"),
    path("logs/export/", views.TrainingLogArchiveExportView.as_view(), name="log_export"),
]
