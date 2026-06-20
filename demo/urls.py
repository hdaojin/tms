from django.urls import path

from . import views

app_name = "demo"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="index"),
    path("list/", views.ListDemoView.as_view(), name="list"),
    path("form/", views.FormDemoView.as_view(), name="form"),
    path("detail/", views.DetailDemoView.as_view(), name="detail"),
    path("htmx/", views.HtmxDemoView.as_view(), name="htmx"),
    path("upload/", views.UploadDemoView.as_view(), name="upload"),
    path("print/", views.PrintDemoView.as_view(), name="print"),
    path("states/", views.StatesDemoView.as_view(), name="states"),
]
