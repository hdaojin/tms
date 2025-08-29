from django.urls import path
from .views import MeetingUploadView, MeetingListView, MeetingDetailView

app_name = 'meeting'

urlpatterns = [
    path('', MeetingListView.as_view(), name='meeting_list'),
    path('upload/', MeetingUploadView.as_view(), name='upload_meeting'),
    path('detail/<int:pk>/', MeetingDetailView.as_view(), name='meeting_detail'),
]
