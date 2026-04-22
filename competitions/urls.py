from django.urls import path

from .views import (
	CompetitionDetailView,
	CompetitionListView,
	CompetitionProjectDetailView,
	CompetitionResultCreateView,
	CompetitorCreateView,
	ExpertCreateView,
	MemberCreateView,
	SkillPositionCreateView,
)


app_name = 'competitions'


urlpatterns = [
	path('', CompetitionListView.as_view(), name='competition_list'),
	path('members/create/', MemberCreateView.as_view(), name='member_create'),
	path('competitors/create/', CompetitorCreateView.as_view(), name='competitor_create'),
	path('experts/create/', ExpertCreateView.as_view(), name='expert_create'),
	path('positions/create/', SkillPositionCreateView.as_view(), name='skillposition_create'),
	path('results/create/', CompetitionResultCreateView.as_view(), name='competitionresult_create'),
	path('projects/<int:pk>/', CompetitionProjectDetailView.as_view(), name='competitionproject_detail'),
	path('<int:pk>/', CompetitionDetailView.as_view(), name='competition_detail'),
]

