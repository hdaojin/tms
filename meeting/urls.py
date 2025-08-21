from django.urls import path
from . import views

app_name = 'meeting'

urlpatterns = [
    path('', views.meeting_list, name='meeting_list'),
    path('upload/', views.upload_meeting, name='upload_meeting'),
    path('detail/<int:meeting_id>/', views.meeting_detail, name='meeting_detail'),
]
