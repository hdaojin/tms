from django.shortcuts import render, redirect 
from django.contrib.auth.decorators import login_not_required
from django.views.generic.detail import DetailView
from django.contrib.auth import authenticate, login
from django.contrib import messages
from accounts.forms import CustomAuthenticationForm

from .models import Page

# Create your views here.
@login_not_required
def homepage(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    # 处理登录表单
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # messages.success(request, f'欢迎回来，{user.get_full_name() or user.username}！')
                return redirect('accounts:profile')
        else:
            messages.error(request, '登录失败，请检查您的用户名和密码。')
    else:
        form = CustomAuthenticationForm()
    
    homepage = Page.objects.filter(slug="index").first()
    if not homepage:
        homepage = Page(title="欢迎使用训练管理系统", content="高效管理训练计划，跟踪训练进度，提升团队协作效率", slug="index")

    template_layout = {
        "header": False,
        "main": True,
        "left_sidebar": False,
        "right_sidebar": False,
        "footer": False,
    } 
    
    return render(request, 'pages/homepage.html', {
        "page": homepage, 
        "title": homepage.title, 
        "template_layout": template_layout,
        "form": form
    })


class PageDetailView(DetailView):
    model = Page

    def get_template_names(self):
        return [f"pages/page_{self.object.template}.html"]
     
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.object.title
        return {"page": context['object'], "title": context['title']}

    def get_queryset(self):
        return Page.objects.filter(slug=self.kwargs['slug'])















