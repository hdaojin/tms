from django.urls import path
from .views import MeetingUploadView, MeetingListView, MeetingDetailView, MeetingDeleteView, MeetingFileContentView, meeting_pdf_inline
from .views import MeetingAudienceView, recipient_search

app_name = 'meetings'

urlpatterns = [
    path('', MeetingListView.as_view(), name='meeting_list'),
    path('upload/', MeetingUploadView.as_view(), name='meeting_upload'),
    path('recipients/search/', recipient_search, name='recipient_search'),
    path('audience/<int:pk>/', MeetingAudienceView.as_view(), name='meeting_audience'),
    path('detail/<int:pk>/', MeetingDetailView.as_view(), name='meeting_detail'),
    path('delete/<int:pk>/', MeetingDeleteView.as_view(), name='meeting_delete'),
    path('pdf_inline/<int:pk>/', meeting_pdf_inline, name='meeting_pdf_inline'),
    path('file/<int:pk>/', MeetingFileContentView.as_view(), name='meeting_file'),
]
