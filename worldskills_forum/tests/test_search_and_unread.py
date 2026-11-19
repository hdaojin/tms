from datetime import timedelta

from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from worldskills_forum.models import ForumSourceRole, ForumTopicReadState

from .base import ForumTestCase


class SearchAndUnreadTests(ForumTestCase):
    def test_feed_orders_by_translation_publish_time_and_searches_both_languages(self):
        topic = self.make_topic()
        older = self.make_post(topic=topic, published_at=timezone.now() - timedelta(days=1), source_url="https://forum.example.com/p/old")
        newer = self.make_post(topic=topic, posted_at=timezone.now() - timedelta(days=10), published_at=timezone.now(), source_url="https://forum.example.com/p/new", original_content="Network infrastructure")
        self.client.force_login(self.reader)
        response = self.client.get(reverse("worldskills_forum:feed"))
        self.assertEqual([post.pk for post in response.context["posts"]], [newer.pk, older.pk])
        self.assertContains(self.client.get(reverse("worldskills_forum:feed"), {"q": "Network"}), "Network infrastructure")
        self.assertContains(self.client.get(reverse("worldskills_forum:feed"), {"q": "中文评分"}), "中文评分说明")

    def test_topic_list_uses_shared_filtering_and_htmx_partial(self):
        target = self.make_topic(
            translated_title="筛选目标主题",
            original_title="Filtering Target Topic",
            source_url="https://forum.example.com/t/filter-target",
        )
        self.make_post(topic=target, source_url="https://forum.example.com/p/filter-target")
        other = self.make_topic(
            competition_year=2025,
            translated_title="其他主题",
            original_title="Other Topic",
            source_url="https://forum.example.com/t/filter-other",
        )
        self.make_post(topic=other, source_url="https://forum.example.com/p/filter-other")
        self.client.force_login(self.reader)

        params = {"q": "目标", "year": "2026"}
        response = self.client.get(reverse("worldskills_forum:topic_list"), params)
        self.assertContains(response, target.translated_title)
        self.assertNotContains(response, other.translated_title)
        self.assertEqual(
            [control["name"] for control in response.context["list_filter_controls"]],
            ["q", "module", "category"],
        )
        toolbar = BeautifulSoup(response.content, "html.parser").select_one("form[hx-trigger]")
        self.assertIsNotNone(toolbar)
        self.assertEqual(toolbar["hx-get"], response.wsgi_request.path)
        self.assertEqual(toolbar["hx-trigger"], "submit")
        self.assertEqual(toolbar.select_one("input, select")["name"], "q")
        self.assertIsNotNone(toolbar.select_one('details[open] select[name="year"]'))
        self.assertIsNotNone(toolbar.select_one('button[type="submit"]'))
        summary = BeautifulSoup(response.content, "html.parser").select_one("#forum-topic-list-active-filters")
        remove_year = summary.select_one('a[aria-label="移除年份：2026"]')
        self.assertNotIn("year=", remove_year["href"])
        self.assertIn("q=", remove_year["href"])
        self.assertNotContains(response, "hx-indicator=", html=False)
        self.assertNotContains(response, "loading-spinner", html=False)
        self.assertContains(response, 'class="list-filter-select select w-full md:select-sm"', html=False)
        self.assertIsNotNone(toolbar.select_one('input.list-filter-search[name="q"]'))
        self.assertContains(response, '<option value="2026" selected>', html=False)
        self.assertNotContains(response, ">筛选</button>", html=False)
        self.assertContains(response, f'href="{reverse("worldskills_forum:topic_list")}">重置</a>', html=False)

        htmx_response = self.client.get(
            reverse("worldskills_forum:topic_list"),
            params,
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(htmx_response.status_code, 200)
        self.assertNotContains(htmx_response, "<!doctype html>", html=False)
        self.assertNotContains(htmx_response, "全部年份")
        self.assertContains(htmx_response, 'hx-swap-oob="true"')
        self.assertContains(htmx_response, target.translated_title)
        self.assertNotContains(htmx_response, other.translated_title)

    def test_feed_classification_keeps_search_and_clears_page(self):
        self.client.force_login(self.reader)
        response = self.client.get(reverse("worldskills_forum:feed"), {"view": "important", "q": "target"})
        soup = BeautifulSoup(response.content, "html.parser")
        toolbar = soup.select_one('form[method="get"]')
        self.assertEqual(toolbar.select_one('input[name="view"]')["value"], "important")
        self.assertFalse(toolbar.has_attr("hx-get"))
        nav = soup.select_one('nav[aria-label="按状态筛选"]')
        self.assertIn("view=important", nav.select_one('[aria-current="true"]')["href"])
        official = nav.select_one('a[href*="view=official"]')
        self.assertIn("q=target", official["href"])
        self.assertNotIn("page=", official["href"])

    def test_topic_list_history_restore_returns_full_toolbar(self):
        self.client.force_login(self.reader)
        response = self.client.get(
            reverse("worldskills_forum:topic_list"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
        )
        self.assertContains(response, "<!doctype html>")
        self.assertContains(response, "高级筛选")
        self.assertNotContains(response, 'hx-swap-oob="true"')


    def test_unread_uses_translation_publish_time(self):
        viewed_at = timezone.now() - timedelta(days=1)
        post = self.make_post(posted_at=timezone.now() - timedelta(days=10), published_at=timezone.now())
        ForumTopicReadState.objects.create(user=self.reader, topic=post.topic, last_viewed_at=viewed_at)
        self.client.force_login(self.reader)
        response = self.client.get(reverse("worldskills_forum:feed"), {"view": "unread"})
        self.assertContains(response, post.topic.translated_title)

    def test_topic_divider_uses_previous_state_then_marks_viewed(self):
        old_time = timezone.now() - timedelta(days=2)
        topic = self.make_topic()
        self.make_post(topic=topic, published_at=old_time - timedelta(hours=1), source_url="https://forum.example.com/p/old")
        self.make_post(topic=topic, posted_at=timezone.now() - timedelta(days=20), published_at=timezone.now(), source_url="https://forum.example.com/p/new")
        ForumTopicReadState.objects.create(user=self.reader, topic=topic, last_viewed_at=old_time)
        self.client.force_login(self.reader)
        response = self.client.get(reverse("worldskills_forum:topic_detail", args=[topic.pk]))
        self.assertContains(response, "你上次看到这里")
        self.assertEqual(len(response.context["new_posts"]), 1)

    def test_first_visit_has_no_divider(self):
        post = self.make_post()
        self.client.force_login(self.reader)
        response = self.client.get(reverse("worldskills_forum:topic_detail", args=[post.topic_id]))
        self.assertNotContains(response, "你上次看到这里")
        self.assertTrue(ForumTopicReadState.objects.filter(user=self.reader, topic=post.topic).exists())

    def test_official_feed_uses_source_role_configuration(self):
        configured_official = ForumSourceRole.objects.create(
            name="赛事官方代表",
            slug="event-official",
            is_official=True,
        )
        post = self.make_post(source_role=configured_official)
        self.client.force_login(self.reader)

        response = self.client.get(reverse("worldskills_forum:feed"), {"view": "official"})

        self.assertContains(response, post.topic.translated_title)
        self.assertContains(response, "赛事官方代表")

    def test_official_feed_uses_post_type_configuration(self):
        from worldskills_forum.models import ForumPostType

        configured_official = ForumPostType.objects.create(
            code="official-technical-update",
            name="官方技术更新",
            is_official=True,
        )
        post = self.make_post(post_type=configured_official)
        self.client.force_login(self.reader)

        response = self.client.get(reverse("worldskills_forum:feed"), {"view": "official"})

        self.assertContains(response, post.topic.translated_title)
        self.assertContains(response, "官方技术更新")
