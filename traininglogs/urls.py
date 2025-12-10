from django.urls import path
from .views import (
    TrainingLogUploadView,
    TraininglogListView,
    TrainingLogDetailView,
    TrainingLogDeleteView,
    traininglog_pdf_inline,
    CoachTraininglogListView,
    CompetitorTraininglogListView,
    TraininglogMonthlyStatView,
)

app_name = 'traininglogs'

urlpatterns = [
    path('list/', TraininglogListView.as_view(), name='traininglog_list'),
    path('coaches/', CoachTraininglogListView.as_view(), name='traininglog_coach_list'),
    path('competitors/', CompetitorTraininglogListView.as_view(), name='traininglog_competitor_list'),
    path('stats/', TraininglogMonthlyStatView.as_view(), name='traininglog_stats'),
    path('upload/', TrainingLogUploadView.as_view(), name='traininglog_upload'),
    path('<int:pk>/', TrainingLogDetailView.as_view(), name='traininglog_detail'),
    path('delete/<int:pk>/', TrainingLogDeleteView.as_view(), name='traininglog_delete'),
    path('pdf-inline/<int:pk>/', traininglog_pdf_inline, name='traininglog_pdf_inline'),
]
