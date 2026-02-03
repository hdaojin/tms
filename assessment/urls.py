from django.urls import path
from . import views

app_name = 'assessment'

urlpatterns = [
    path('list', views.assessment_list, name='list'),
    path('<int:pk>/', views.assessment_detail, name='detail'),
    path('file-upload/<int:module_id>/', views.assessment_file_upload, name='file_upload'),
    path('file-upload/<int:module_id>/delete/<str:field_name>/', views.delete_module_file, name='delete_module_file'),
    path('attachment/<int:attachment_id>/delete/', views.delete_attachment, name='delete_attachment'),
]
