from django.urls import path
from .views import homepage, PageDetailView



app_name = 'pages'

urlpatterns = [
    path('', homepage, name='homepage'),
    path('<slug:slug>/', PageDetailView.as_view(), name='page_detail'),
]