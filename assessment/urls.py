from django.urls import path
from . import views

app_name = 'assessment'

urlpatterns = [
    path('list', views.assessment_list, name='list'),
    path('<int:pk>/', views.assessment_detail, name='detail'),
    path('module/<int:module_id>/scores/', views.module_score_entry, name='module_score_entry'),
    path('module/<int:module_id>/score-lock/', views.module_score_lock, name='module_score_lock'),
    path('module/<int:module_id>/material-lock/', views.module_material_lock, name='module_material_lock'),
    path('file-upload/<int:module_id>/', views.assessment_file_upload, name='file_upload'),
    path('file-upload/<int:module_id>/delete/<str:field_name>/', views.delete_module_file, name='delete_module_file'),
    path('attachment/<int:attachment_id>/delete/', views.delete_attachment, name='delete_attachment'),
]
