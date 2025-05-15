from django.urls import path
from django.contrib.auth import views as auth_views
from .views import account_signup, account_profile, generate_invitation

app_name = 'accounts'

template_layout = {
    "header": False,
    "main": True,
    "left_sidebar": False,
    "right_sidebar": False,
    "footer": True,
}

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        extra_context={'title': '登录', 'template_layout': template_layout},
        ), name="login"),
    path('profile/', account_profile, name="profile"),
    path('logout/', auth_views.logout_then_login, name="logout"),
    path('signup/', account_signup, name="signup"),
    path('generate-invite/', generate_invitation, name='generate_invitation'),
]
