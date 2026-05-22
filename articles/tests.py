from unittest import skipUnless

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .apps import CmsConfig

ARTICLES_ENABLED = 'articles' in settings.INSTALLED_APPS

if ARTICLES_ENABLED:
	from .models import Article


@skipUnless(ARTICLES_ENABLED, 'articles APP 当前已停用。')
class ArticlesExperimentMarkerTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='article-user', password='testpass123')
		self.article = Article.objects.create(
			title='实验文章',
			slug='test-article',
			author=self.user,
			content='这是一个实验模块页面。',
			status=Article.Status.PUBLISHED,
			publish_date=timezone.now(),
		)
		self.draft_article = Article.objects.create(
			title='草稿文章',
			slug='draft-article',
			author=self.user,
			content='这是一篇草稿。',
			status=Article.Status.DRAFT,
			publish_date=timezone.now(),
		)
		self.archived_article = Article.objects.create(
			title='归档文章',
			slug='archived-article',
			author=self.user,
			content='这是一篇归档文章。',
			status=Article.Status.ARCHIVED,
			publish_date=timezone.now(),
		)
		self.client.force_login(self.user)

	def test_app_config_marks_module_as_experimental(self):
		self.assertIn('低优先实验模块', CmsConfig.verbose_name)

	def test_article_list_shows_experimental_notice(self):
		response = self.client.get(reverse('articles:list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '低优先实验模块')
		self.assertContains(response, '文章模块当前仅作为低优先实验模块保留')
		self.assertContains(response, self.article.title)
		self.assertNotContains(response, self.draft_article.title)
		self.assertNotContains(response, self.archived_article.title)

	def test_article_detail_shows_experimental_notice(self):
		response = self.client.get(reverse('articles:detail', kwargs={'slug': self.article.slug}))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '低优先实验模块')
		self.assertContains(response, '文章详情')
