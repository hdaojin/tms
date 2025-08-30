from django.shortcuts import render
from django.contrib.auth.decorators import login_not_required # type: ignore

from .forms import CustomUserCreationForm
from .utils import generate_invitation_code
from common.decorators import superuser_required


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


def account_profile(request):
    return render(request, 'accounts/profile.html', {
        'title': '个人信息',
        'title_icon': 'icon-[tabler--user-circle]',
        'user': request.user
    })

@superuser_required
def generate_invitation(request):
    code = generate_invitation_code()
    return render(request, 'accounts/generate_invite.html', {
        'title': '生成邀请码',
        'code': code,
    })