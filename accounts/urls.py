from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    CustomLoginView,
    RoleListView,
    UserDetailView,
    UserListView,
    account_home,
    account_profile,
    account_signup,
    generate_invitation,
)
from .forms import CustomAuthenticationForm

app_name = 'accounts'


urlpatterns = [
    path('home/', account_home, name="home"),
    path('login/', CustomLoginView.as_view(
        template_name='accounts/login.html',
        authentication_form=CustomAuthenticationForm,
        redirect_authenticated_user=True,
        extra_context={'title': '登录'},
    ), name="login"),
    path('profile/', account_profile, name="profile"),
    path('logout/', auth_views.logout_then_login, name="logout"),
    path('signup/', account_signup, name="signup"),
    path('generate-invite/', generate_invitation, name='generate_invitation'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('roles/', RoleListView.as_view(), name='role_list'),
]
