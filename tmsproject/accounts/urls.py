from django.urls import path
from django.contrib.auth import views as auth_views

app_name = 'accounts'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name="accounts/login.html", extra_context={"is_login_page": True}), name="login"),
    path('logout/', auth_views.logout_then_login, name="logout"),
]
