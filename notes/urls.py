from django.urls import path

from .views import NoteDetailView, NotesRepoListView, note_asset_view

app_name = "notes"

urlpatterns = [
    path("", NotesRepoListView.as_view(), name="repo_list"),
    path("<str:repo>/", NoteDetailView.as_view(), name="note_repo_index"),
    path("<str:repo>/<path:slug>/", NoteDetailView.as_view(), name="note_detail"),
]
