from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "home/homepage.html"
    extra_context = {"title": "首页", "title_icon": "icon-[tabler--home]"}
