from django.urls import path
from . import views

app_name = 'skills'

urlpatterns = [
    path('exam-points/create/', views.ExamPointCreateView.as_view(), name='exam_point_create'),
    path(
        'htmx/exam-points/dependencies/',
        views.exam_point_dependency_fields,
        name='exam_point_dependency_fields',
    ),
    path(
        'htmx/exam-points/topic-suggestions/',
        views.exam_point_topic_suggestions,
        name='exam_point_topic_suggestions',
    ),
    path(
        'htmx/exam-points/name-suggestions/',
        views.exam_point_name_suggestions,
        name='exam_point_name_suggestions',
    ),
    path('', views.SkillListView.as_view(), name='skill_list'),
]
