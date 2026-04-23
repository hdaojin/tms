from django.urls import path
from .views import MeetingUploadView, MeetingListView, MeetingDetailView, MeetingDeleteView, meeting_pdf_inline

app_name = 'meetings'

urlpatterns = [
    path('', MeetingListView.as_view(), name='meeting_list'),
    path('upload/', MeetingUploadView.as_view(), name='meeting_upload'),
    path('detail/<int:pk>/', MeetingDetailView.as_view(), name='meeting_detail'),
    path('delete/<int:pk>/', MeetingDeleteView.as_view(), name='meeting_delete'),
    path('pdf_inline/<int:pk>/', meeting_pdf_inline, name='meeting_pdf_inline'),
]
