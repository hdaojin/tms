from django.urls import path

from .views import TrainingCycleDetailView, TrainingCycleListView


app_name = 'competition_standards'

urlpatterns = [
    path('', TrainingCycleListView.as_view(), name='list'),
    path('<int:pk>/', TrainingCycleDetailView.as_view(), name='detail'),
]