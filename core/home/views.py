from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.urls import reverse

from core.utils.mixins import TitleMixin
from accounts.forms import CustomAuthenticationForm


class HomeView(TitleMixin, TemplateView):
    template_name = "home/homepage.html"
    title = "首页"
    title_icon = "icon-[tabler--home]"
    extra_context = {
        "login_form": CustomAuthenticationForm(),
    }
    
    def dispatch(self, request, *args, **kwargs):
        """如果用户已登录，则重定向到个人资料页面"""
        if request.user.is_authenticated:
            return redirect(reverse('accounts:home'))
        return super().dispatch(request, *args, **kwargs)
