from django.contrib.auth.decorators import login_not_required  # type: ignore
from django.urls import path

from . import views

app_name = 'event_countdown'

urlpatterns = [
    path('', login_not_required(views.countdown_screen), name='countdown'),
    path('<slug:slug>/', login_not_required(views.countdown_screen_by_slug), name='countdown_detail'),
]
