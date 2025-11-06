from django.urls import path
from django.contrib.auth import views as auth_views
from .views import account_signup, account_home, account_profile, generate_invitation

app_name = 'accounts'


urlpatterns = [
    path('', account_home, name="home"),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html', redirect_authenticated_user=True,  extra_context={'title': '登录' },), name="login"),
    path('profile/', account_profile, name="profile"),
    path('logout/', auth_views.logout_then_login, name="logout"),
    path('signup/', account_signup, name="signup"),
    path('generate-invite/', generate_invitation, name='generate_invitation'),
]
