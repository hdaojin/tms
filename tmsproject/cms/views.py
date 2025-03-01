from django.shortcuts import render

# Create your views here.
from .models import Page

def about(request):
    page = Page.objects.get(permalink='about')
    return render(request, 'cms/page.html', {'page': page})
