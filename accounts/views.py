from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_not_required  # type: ignore
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Case, CharField, Count, F, OuterRef, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.views.generic import DetailView
from django_tables2 import SingleTableView

from .forms import CustomUserCreationForm, ProfileForm
from .services.users import (
    ROLE_STAFF,
    ROLE_SUPERUSER,
    ROLE_UNASSIGNED,
    get_user_role_badges,
)
from .services.registration import apply_default_registration_group
from .services.profiles import update_profile
from .tables import PermissionBundleReferenceTable, RoleListTable, UserListTable
from core.permissions import get_permission_bundle_specs
from core.utils.invitation import generate_invitation_code
from core.utils.decorators import superuser_required
from core.utils.mixins import TitleMixin
from .models import UserProfile
from .services.user_management import filter_users
from .user_management_forms import UserActionForm, UserFilterForm
from core.utils.listing import FilterableListMixin, ListFilterSpec

User = get_user_model()


class CustomLoginView(LoginView):
    """登录视图：勾选“记住我”时保持默认会话有效期，不勾选则关闭浏览器即失效。"""

    def form_valid(self, form):
        auth_login(self.request, form.get_user())
        if not self.request.POST.get("remember_me"):
            self.request.session.set_expiry(0)
        return redirect(self.get_success_url())


@login_not_required
def account_signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                # 姓名已由表单处理（last_name 和 first_name）
                # 新注册用户默认不激活（例如等待邮件激活）
                user.is_active = False
                user.save()
                apply_default_registration_group(user)
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
        'title': '功能面板',
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
    """用户查看和编辑个人资料。锁定后不可修改，需管理员解锁。"""

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action not in ('save', 'lock'):
            raise PermissionDenied
        try:
            form = update_profile(actor=request.user, target_id=request.user.pk, action=action, data=request.POST)
        except ValidationError as exc:
            messages.info(request, '；'.join(exc.messages))
            return redirect('accounts:profile')
        if not form.errors:
            messages.success(request, "个人资料已保存并锁定，如需更改请联系管理员解锁。" if action == 'lock' else "个人资料已保存。")
            return redirect('accounts:profile')
        profile = form.instance
    else:
        profile, _created = UserProfile.objects.get_or_create(user=request.user)
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


class UserListView(FilterableListMixin, TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, SingleTableView):
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

    def get_list_filter_specs(self):
        filters = UserFilterForm()
        return (
            ListFilterSpec("q", "搜索用户", "search", placeholder="账号、完整姓名或学号"),
            ListFilterSpec("active", "激活状态", "select", choices=filters.fields["active"].choices[1:], empty_label="全部状态"),
            ListFilterSpec("role", "角色", "select", choices=filters.fields["role"].choices[1:], empty_label="全部角色"),
        )

    def apply_custom_filters(self, queryset):
        filters = UserFilterForm(self.request.GET)
        return filter_users(queryset, filters.cleaned_data) if filters.is_valid() else queryset.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["management_form"] = UserActionForm()
        return context

    def get_table_kwargs(self):
        kwargs = super().get_table_kwargs()
        if not self.request.user.is_superuser:
            kwargs["exclude"] = ("selection",)
        return kwargs

    def get_base_queryset(self):
        """获取全部用户，并预加载 profile 与角色信息以优化查询。"""
        first_group_name = (
            Group.objects.filter(user=OuterRef("pk"))
            .order_by("name")
            .values("name")[:1]
        )
        return (
            User.objects.select_related("profile")
            .prefetch_related("groups")
            .annotate(
                role_sort=Case(
                    When(is_superuser=True, then=Value(ROLE_SUPERUSER)),
                    When(is_staff=True, then=Value(ROLE_STAFF)),
                    default=Coalesce(
                        Subquery(first_group_name, output_field=CharField()),
                        Value(ROLE_UNASSIGNED),
                        output_field=CharField(),
                    ),
                    output_field=CharField(),
                )
            )
            .order_by(
                "-is_active",
                F("profile__join_date").desc(nulls_last=True),
                F("pk").desc(),
            )
        )


class RoleListView(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, SingleTableView):
    """显示所有角色列表（包含 GroupProfile 信息）。"""

    model = Group
    table_class = RoleListTable
    template_name = "accounts/role_list.html"
    permission_required = "auth.view_group"
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["permission_bundle_table"] = PermissionBundleReferenceTable(
            get_permission_bundle_specs()
        )
        return context


class UserDetailView(TitleMixin, LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """显示用户详细信息。

    需要 'accounts.view_all_profiles' 权限才能访问。
    """

    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "target_user"
    permission_required = "accounts.view_all_profiles"
    raise_exception = True
    title = "{display_name}的详细信息"
    title_icon = "icon-[tabler--user-circle]"

    def get_queryset(self):
        return User.objects.select_related("profile").prefetch_related("groups")

    def post(self, request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_superuser:
            raise PermissionDenied
        self.object = self.get_object()
        action = request.POST.get("action", "save")
        try:
            form = update_profile(actor=request.user, target_id=self.object.pk, action=action, data=request.POST)
        except ValidationError as exc:
            messages.error(request, '；'.join(exc.messages))
            return redirect("accounts:user_detail", pk=self.object.pk)
        if form is None or not form.errors:
            message = {
                "save": "用户资料已保存。",
                "lock": "用户资料已保存并锁定。",
                "unlock": "用户资料已解锁，用户本人也可重新编辑。",
            }[action]
            messages.success(request, message)
            return redirect("accounts:user_detail", pk=self.object.pk)
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        form = kwargs.pop("form", None)
        context = super().get_context_data(**kwargs)
        target_user = context["target_user"]
        if form is None:
            profile, _ = UserProfile.objects.get_or_create(user=target_user)
            form = ProfileForm(instance=profile)
        else:
            profile = form.instance
        can_manage_profile = self.request.user.is_active and self.request.user.is_superuser
        if not can_manage_profile:
            for field in form.fields.values():
                field.disabled = True
        context["form"] = form
        context["profile"] = profile
        context["role_badges"] = get_user_role_badges(target_user, size="badge-lg")
        context["can_manage_profile"] = can_manage_profile
        context["can_edit_profile"] = can_manage_profile and not profile.locked
        return context
