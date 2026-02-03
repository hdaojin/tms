from django.urls import path
from . import views

app_name = 'demo'

urlpatterns = [
    path('', views.ComponentsDemoView.as_view(), name='index'),
    path('file-upload/', views.FileUploadDemoView.as_view(), name='file_upload'),
]
