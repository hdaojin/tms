from django.urls import path, re_path
from . import views

app_name = 'notes'

urlpatterns = [
    path('subdirectories/', views.list_notes_directories, name='list_directories'),
    re_path(r'^(?P<subdirectory>.*)/readme/$', views.get_readme, name='get_readme'),
    re_path(r'^(?P<subdirectory>.*)/(?P<note_file>.*)/$', views.get_note, name='get_note'),
]
