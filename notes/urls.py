from django.urls import path

from .management_views import NoteRepoManagementForm, NoteRepoManagementList
from .views import note_detail_view, notes_repo_list_view

app_name = "notes"

urlpatterns = [
    path("", notes_repo_list_view, name="repo_list"),
    # @ 不属于仓库访问标识的允许字符，管理入口不会占用已有笔记链接。
    path("@manage/", NoteRepoManagementList.as_view(), name="repo_manage_list"),
    path("@manage/add/", NoteRepoManagementForm.as_view(), name="repo_manage_add"),
    path("@manage/<int:pk>/edit/", NoteRepoManagementForm.as_view(), name="repo_manage_edit"),
    path("<str:repo>/", note_detail_view, name="note_repo_index"),
    path("<str:repo>/<path:slug>/", note_detail_view, name="note_detail"),
]
