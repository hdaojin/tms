from django.urls import path

from . import views

app_name = "ai_models"

urlpatterns = [
    path("", views.ModelListView.as_view(), name="list"),
    path("new/", views.ModelEditView.as_view(), name="create"),
    path("providers/", views.ProviderListView.as_view(), name="providers"),
    path("providers/<slug:provider>/", views.ProviderCatalogView.as_view(), name="provider"),
    path("providers/<slug:provider>/new/", views.ProviderOptionView.as_view(), name="option_create"),
    path(
        "providers/<slug:provider>/fallback/",
        views.ProviderOptionView.as_view(),
        {"fallback": True},
        name="option_fallback",
    ),
    path("providers/<slug:provider>/<int:pk>/edit/", views.ProviderOptionView.as_view(), name="option_edit"),
    path("public/", views.ModerationView.as_view(), name="moderation"),
    path("public/<int:pk>/delist/", views.ModerationActionView.as_view(), {"delisted": True}, name="delist"),
    path("public/<int:pk>/restore/", views.ModerationActionView.as_view(), {"delisted": False}, name="restore"),
    path("<int:pk>/", views.ModelDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ModelEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ModelDeleteView.as_view(), name="delete"),
    path("<int:pk>/test/", views.ModelActionView.as_view(), {"action": "test"}, name="test"),
    path("<int:pk>/share/", views.ModelActionView.as_view(), {"action": "share"}, name="share"),
    path("<int:pk>/default/", views.DefaultModelView.as_view(), name="default"),
]
