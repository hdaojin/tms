from django.shortcuts import render
from django.views.generic import ListView
from django.views.generic import DetailView
# from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Post
# Create your views here.

def index(request):
    context = {
        'title': 'Hello, Django!',
        'content': 'Welcome to the Django project.'
    }
    return render(request, 'cms/index.html', context)

class PostListView(LoginRequiredMixin, ListView):
    model = Post
    template_name = 'cms/post_list.html'
    context_object_name = 'posts'
    ordering = ['-created']

class PostDetailView(LoginRequiredMixin, DetailView):
    model = Post
    template_name = 'cms/post_detail.html'
    context_object_name = 'post'




