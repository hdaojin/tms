from django.shortcuts import render
from django.contrib.auth.decorators import login_not_required

# Create your views here.

@login_not_required
def home(request):
    context = {
        'is_homepage': True,
        'title': None,
        'content': {
            'title': 'Welcome to TMS',
            'description': 'TMS (Training Management System) is a web-based application designed to help users manage their training logs and related activities.',
        }
    }

    return render(request, 'homepage/index.html', context)
