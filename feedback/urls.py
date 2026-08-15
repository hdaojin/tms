from django.urls import path

from . import views


app_name = "feedback"

urlpatterns = [
    path("", views.FeedbackListView.as_view(), name="list"),
    path("new/", views.FeedbackCreateView.as_view(), name="create"),
    path("attachments/<int:pk>/", views.FeedbackAttachmentView.as_view(), name="attachment"),
    path("<int:pk>/", views.FeedbackDetailView.as_view(), name="detail"),
    path("<int:pk>/reply/", views.FeedbackReplyView.as_view(), name="reply"),
    path("<int:pk>/manage/", views.FeedbackManageView.as_view(), name="manage"),
]
