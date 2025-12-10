from django.urls import path
from .views import NoticeCreateView, NoticeDetailView, NoticeListView, NoticeDeleteView

app_name = 'notices'

urlpatterns = [
    path('list/', NoticeListView.as_view(), name='notice_list'),
    path('create/', NoticeCreateView.as_view(), name='notice_create'),
    path('<int:pk>/', NoticeDetailView.as_view(), name='notice_detail'),
    path('delete/<int:pk>/', NoticeDeleteView.as_view(), name='notice_delete'),
]