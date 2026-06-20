from django.urls import path

from .views import note_detail_view, note_print_view, notes_repo_list_view

app_name = "notes"

urlpatterns = [
    path("", notes_repo_list_view, name="repo_list"),
    path("<str:repo>/", note_detail_view, name="note_repo_index"),
    path("<str:repo>/<path:slug>/print/", note_print_view, name="note_print"),
    path("<str:repo>/<path:slug>/", note_detail_view, name="note_detail"),
]
