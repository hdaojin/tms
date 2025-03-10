from django.shortcuts import render
from django.contrib.auth.decorators import login_not_required

# Create your views here.

@login_not_required
def home(request):
    context = {
        'is_homepage': True,
        'title': 'Home',
        'content': 'Welcome to the homepage of the TMS project.'
    }

    return render(request, 'homepage/index.html', context)
