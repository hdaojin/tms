from django.urls import path
from .views import TrainingLogUploadView, TraininglogListView 

app_name = 'traininglogs'

urlpatterns = [
    path('', TraininglogListView.as_view(), name='traininglog_list'),
    path('upload/', TrainingLogUploadView.as_view(), name='traininglog_upload'),
]
