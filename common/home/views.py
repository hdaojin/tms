from django.views.generic import TemplateView
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.urls import reverse


class HomeView(TemplateView):
    template_name = "home/homepage.html"
    extra_context = {
        "title": "首页", 
        "title_icon": "icon-[tabler--home]",
        "login_form": AuthenticationForm(),
    }
    
    def dispatch(self, request, *args, **kwargs):
        """如果用户已登录，则重定向到个人资料页面"""
        if request.user.is_authenticated:
            return redirect(reverse('accounts:profile'))
        return super().dispatch(request, *args, **kwargs)
