from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_not_required  # type: ignore
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count
from django.views.generic import DetailView
from django_tables2 import SingleTableView

from .forms import CustomUserCreationForm, ProfileForm
from .services.users import get_user_role_badges
from .tables import RoleListTable, UserListTable
from core.utils.invitation import generate_invitation_code
from core.utils.decorators import superuser_required
from core.utils.mixins import TitleMixin
from .models import UserProfile

User = get_user_model()


@login_not_required
def account_signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # 姓名已由表单处理（last_name 和 first_name）
            # 新注册用户默认不激活（例如等待邮件激活）
            user.is_active = False
            user.save()
            # 此处可添加发送激活邮件逻辑
            return render(request, 'accounts/signup_done.html', {
                'title': "注册成功",
                'new_user': user
            }) 
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/signup.html', {
        'form': form,
        'title': "新用户注册",
    })


def account_home(request):
    return render(request, 'accounts/home.html', {
        'title': '用户中心',
        'title_icon': 'icon-[tabler--user]',
        'user': request.user
    })


@superuser_required
def generate_invitation(request):
    code = generate_invitation_code()
    return render(request, 'accounts/generate_invite.html', {
        'title': '生成邀请码',
        'title_icon': 'icon-[tabler--user-plus]',
        'code': code,
    })


@login_required
def account_profile(request):
    """用户查看和编辑个人资料。锁定后不可修改，需管理员在后台解锁。"""

    profile, _created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # 若已锁定则禁止任何提交
        if profile.locked:
            messages.info(request, "资料已锁定，如需修改请联系管理员在后台解锁。")
            return redirect('accounts:profile')
        
        action = request.POST.get('action', 'save')
        form = ProfileForm(request.POST, instance=profile, request=request)
        
        if form.is_valid():
            obj = form.save(commit=False)
            # 锁定操作：保存并锁定
            if action == 'lock':
                obj.locked = True
                obj.save()
                messages.success(request, "个人资料已保存并锁定，无法再次修改。如需更改请联系管理员解锁。")
            else:
                # 仅保存
                obj.save()
                messages.success(request, "个人资料已保存。")
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=profile, request=request)

    can_edit = (not profile.locked)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
        'role_badges': get_user_role_badges(request.user, size='badge-lg'),
        'title': '个人资料',
        'title_icon': 'icon-[tabler--user-circle]',
        'can_edit': can_edit,
    })


class UserListView(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, SingleTableView):
    """显示所有用户列表（包含 Profile 信息）。

    需要 'accounts.view_all_profiles' 权限才能访问。
    """

    model = User
    table_class = UserListTable
    template_name = "accounts/user_list.html"
    permission_required = "accounts.view_all_profiles"
    raise_exception = True
    paginate_by = 20
    title = "用户列表"
    title_icon = "icon-[tabler--users]"

    def get_queryset(self):
        """获取全部用户，并预加载 profile 与角色信息以优化查询。"""
        return User.objects.prefetch_related("groups").order_by("-date_joined", "-pk")


class RoleListView(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, SingleTableView):
    """显示所有角色列表（包含 GroupProfile 信息）。"""

    model = Group
    table_class = RoleListTable
    template_name = "accounts/role_list.html"
    permission_required = "accounts.view_all_profiles"
    raise_exception = True
    paginate_by = 20
    title = "角色列表"
    title_icon = "icon-[tabler--users]"

    def get_queryset(self):
        return (
            Group.objects.select_related("profile")
            .annotate(user_total=Count("user", distinct=True))
            .order_by("name")
        )


class UserDetailView(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """显示用户详细信息。

    需要 'accounts.view_all_profiles' 权限才能访问。
    """

    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "target_user"
    permission_required = "accounts.view_all_profiles"
    raise_exception = True
    title = "{first_name}的详细信息"
    title_icon = "icon-[tabler--user-circle]"

    def get_queryset(self):
        return User.objects.select_related("profile").prefetch_related("groups")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_user = context["target_user"]
        profile, _ = UserProfile.objects.get_or_create(user=target_user)
        # 复用 ProfileForm，设置为只读模式
        form = ProfileForm(instance=profile)
        for field in form.fields.values():
            field.disabled = True
        context["form"] = form
        context["profile"] = profile
        context["role_badges"] = get_user_role_badges(target_user, size="badge-lg")
        return context
