from django.urls import path
from django.contrib.auth import views as auth_views
from .views import account_signup, account_profile

app_name = 'accounts'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        extra_context={'title': None}
        ), name="login"),
    path('profile/', account_profile, name="profile"),
    path('logout/', auth_views.logout_then_login, name="logout"),
    path('signup/', account_signup, name="signup"),
]
