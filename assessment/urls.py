from django.urls import path
from . import views

app_name = 'assessment'

urlpatterns = [
    path('', views.assessment_list, name='list'),
    path('<int:pk>/', views.assessment_detail, name='detail'),
]
