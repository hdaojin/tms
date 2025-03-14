from django.urls import path
from . import views

app_name = 'articles'

urlpatterns = [
    path('', views.ArticleListView.as_view(), name='list'),
    # path('<int:pk>/', views.ArticleDetailView.as_view(), name='detail'),
    path('<slug:slug>/', views.ArticleDetailView.as_view(), name='detail'),
    # path('category/<slug:slug>/', views.CategoryArticleListView.as_view(), name='category'),
    # path('tag/<slug:slug>/', views.TagArticleListView.as_view(), name='tag'),
]