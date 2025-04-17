from django.shortcuts import render
from django.contrib.auth.decorators import login_not_required

from .forms import CustomUserCreationForm

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
                'title': None,
                'user': user
            }) 
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/signup.html', {
        'form': form,
        'title': None
    })


# @login_required
def account_profile(request):
    return render(request, 'accounts/profile.html', {
        'title': '个人信息',
        'user': request.user
    })