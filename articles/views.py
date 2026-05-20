from django.views.generic import ListView
from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Article


class ArticleExperimentMixin:
    experimental_module_label = '低优先实验模块'
    experimental_module_notice = '文章模块当前仅作为低优先实验模块保留，界面、流程和权限规则后续都可能继续调整。'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['experimental_module_label'] = self.experimental_module_label
        context['experimental_module_notice'] = self.experimental_module_notice
        return context


class ArticleListView(ArticleExperimentMixin, LoginRequiredMixin, ListView):
    model = Article
    template_name = 'articles/article_list.html'
    context_object_name = 'articles'
    ordering = ['-publish_date']


class ArticleDetailView(ArticleExperimentMixin, LoginRequiredMixin, DetailView):
    model = Article
    template_name = 'articles/article_detail.html'
    context_object_name = 'article'

    def get_queryset(self):
        return Article.objects.filter(status=Article.Status.PUBLISHED)
    

    

