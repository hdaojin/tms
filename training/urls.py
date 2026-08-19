from django.urls import path
from . import views

app_name = "training"
urlpatterns = [
    path("", views.TrainingCycleListView.as_view(), name="cycle_list"),
    path("cycles/create/", views.TrainingCycleCreateView.as_view(), name="cycle_create"),
    path("cycles/<int:pk>/", views.TrainingCycleDetailView.as_view(), name="cycle_detail"),
    path("cycles/<int:pk>/edit/", views.TrainingCycleUpdateView.as_view(), name="cycle_edit"),
    path("plans/", views.TrainingPlanListView.as_view(), name="plan_list"),
    path("plans/create/", views.TrainingPlanCreateView.as_view(), name="plan_create"),
    path("plans/<int:pk>/", views.TrainingPlanDetailView.as_view(), name="plan_detail"),
    path("plans/<int:pk>/edit/", views.TrainingPlanUpdateView.as_view(), name="plan_edit"),
    path("tasks/", views.TrainingTaskListView.as_view(), name="task_list"),
    path("tasks/create/", views.TrainingTaskCreateView.as_view(), name="task_create"),
    path("tasks/<int:pk>/", views.TrainingTaskDetailView.as_view(), name="task_detail"),
    path("tasks/<int:pk>/edit/", views.TrainingTaskUpdateView.as_view(), name="task_edit"),
    path("my/", views.MyTrainingView.as_view(), name="my_training"),
    path("executions/", views.TaskExecutionListView.as_view(), name="execution_list"),
    path("executions/<int:pk>/", views.TaskExecutionDetailView.as_view(), name="execution_detail"),
    path("executions/<int:pk>/edit/", views.TaskExecutionUpdateView.as_view(), name="execution_edit"),
    path("executions/<int:pk>/feedback/", views.CoachFeedbackView.as_view(), name="execution_feedback"),
    path("logs/", views.TrainingLogListView.as_view(), name="log_list"),
    path("logs/create/", views.TrainingLogCreateView.as_view(), name="log_create"),
    path("logs/<int:pk>/", views.TrainingLogDetailView.as_view(), name="log_detail"),
    path("logs/<int:pk>/edit/", views.TrainingLogUpdateView.as_view(), name="log_edit"),
    path("logs/<int:pk>/download/", views.TrainingLogDownloadView.as_view(), name="log_download"),
    path("logs/export/", views.TrainingLogArchiveExportView.as_view(), name="log_export"),
]
