from django.urls import path
from . import views

app_name = 'assessment'

urlpatterns = [
    path('list', views.assessment_list, name='list'),
    path('<int:pk>/', views.assessment_detail, name='detail'),
    path('file-upload/', views.assessment_file_upload_list, name='file_upload_list'),
    path('file-upload/<int:module_id>/', views.assessment_file_upload, name='file_upload'),
]
