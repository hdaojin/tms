from django.urls import path

from .views import samba_account_view

app_name = 'samba'

urlpatterns = [
    path("accounts/", samba_account_view, name="samba-account")
]
