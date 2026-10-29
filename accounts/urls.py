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
from .role_views import RoleEditView, UserPermissionView, UserRolesView
from .user_management_views import UserManagementView

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
    path('users/manage/', UserManagementView.as_view(), name='user_manage'),
    path('users/<int:pk>/manage/', UserManagementView.as_view(), name='user_manage_single'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('roles/', RoleListView.as_view(), name='role_list'),
    path('roles/create/', RoleEditView.as_view(), name='role_create'),
    path('roles/<int:pk>/edit/', RoleEditView.as_view(), name='role_edit'),
    path('roles/<int:pk>/copy/', RoleEditView.as_view(copying=True), name='role_copy'),
    path('users/<int:pk>/permissions/', UserPermissionView.as_view(), name='user_permissions'),
    path('users/<int:pk>/roles/', UserRolesView.as_view(), name='user_roles'),
]
