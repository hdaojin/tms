from django.urls import path

from . import views


app_name = "worldskills_forum"

urlpatterns = [
    path("", views.ForumFeedView.as_view(), name="feed"),
    path("important/", views.ImportantFeedView.as_view(), name="important_feed"),
    path("official/", views.OfficialFeedView.as_view(), name="official_feed"),
    path("unread/", views.UnreadFeedView.as_view(), name="unread_feed"),
    path("topics/", views.ForumTopicListView.as_view(), name="topic_list"),
    path("topics/create/", views.ForumTopicCreateView.as_view(), name="topic_create"),
    path("topics/<int:pk>/", views.ForumTopicDetailView.as_view(), name="topic_detail"),
    path("topics/<int:pk>/edit/", views.ForumTopicUpdateView.as_view(), name="topic_edit"),
    path("topics/<int:pk>/delete/", views.ForumTopicDeleteView.as_view(), name="topic_delete"),
    path("topics/<int:topic_pk>/posts/create/", views.ForumPostTranslationCreateView.as_view(), name="post_create"),
    path("posts/<int:pk>/edit/", views.ForumPostTranslationUpdateView.as_view(), name="post_edit"),
    path("posts/<int:pk>/delete/", views.ForumPostDeleteView.as_view(), name="post_delete"),
    path("posts/<int:post_pk>/attachments/", views.ForumPostAttachmentManageView.as_view(), name="attachment_manage"),
    path("attachments/<int:pk>/delete/", views.ForumAttachmentDeleteView.as_view(), name="attachment_delete"),
    path("attachments/<int:pk>/content/", views.ForumAttachmentContentView.as_view(), name="attachment_content"),
    path("workbench/", views.ForumTranslationWorkbenchView.as_view(), name="workbench"),
]
