from django.shortcuts import render, redirect 
from django.contrib.auth.decorators import login_not_required
from django.views.generic.detail import DetailView

from .models import Page

# Create your views here.
@login_not_required
def homepage(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    homepage = Page.objects.filter(slug="index").first()
    if not homepage:
        homepage = Page(title="Welcome", content="Welcome to TMS(Training Management System)", slug="index")

    template_layout = {
        "header": False,
        "main": True,
        "left_sidebar": False,
        "right_sidebar": False,
        "footer": False,
    } 
    return render(request, 'pages/homepage.html', {"page": homepage, "title": homepage.title, "template_layout": template_layout})


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















