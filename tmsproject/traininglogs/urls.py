from django.urls import path
from . import views

app_name = 'traininglogs'

urlpatterns = [
    path('', views.training_logs, name='list_training_logs'),
    path('upload/', views.upload_training_log, name='upload_training_log'),
    path('view/<int:log_id>/', views.view_training_log, name='view_training_log'),
    path('delete/<int:log_id>/', views.delete_training_log, name='delete_training_log'),
    path('statistics/', views.training_log_statistics, name='training_log_statistics'),
]