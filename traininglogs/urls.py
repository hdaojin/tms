from django.urls import path
from .views import TrainingLogUploadView, TrainingLogListView, TrainingLogDetailView, traininglog_pdf_inline

app_name = 'traininglogs'

urlpatterns = [
    path('', TrainingLogListView.as_view(), name='traininglog_list'),
    path('upload/', TrainingLogUploadView.as_view(), name='traininglog_upload'),
    path('<int:pk>/', TrainingLogDetailView.as_view(), name='traininglog_detail'),
    path('pdf_inline/<int:pk>/', traininglog_pdf_inline, name='traininglog_pdf_inline'),
]
