from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_not_required # type: ignore

from .forms import CustomUserCreationForm, ProfileForm
from common.utils.invitation import generate_invitation_code
from common.decorators import superuser_required
from .models import UserProfile


@login_not_required
def account_signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # 设置用户姓名，可根据需要拆分为 first_name 与 last_name
            user.first_name = form.cleaned_data.get("full_name")
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
    """用户查看和编辑个人资料：提交成功后锁定, 不可再次修改。"""

    profile, _created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # 前台行为与管理员无关：若已锁定则禁止提交
        if profile.locked:
            messages.info(request, "资料已锁定，如需修改请联系管理员在后台解锁。")
            return redirect('accounts:profile')
        form = ProfileForm(request.POST, instance=profile, request=request)
        if form.is_valid():
            obj = form.save(commit=False)
            # 提交后一律锁定
            obj.locked = True
            obj.save()
            messages.success(request, "个人资料已保存并锁定，无法再次修改。")
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=profile, request=request)

    can_edit = (not profile.locked)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
        'title': '个人资料',
        'title_icon': 'icon-[tabler--user-circle]',
        'can_edit': can_edit,
    })
