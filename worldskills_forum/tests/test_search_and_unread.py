from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from worldskills_forum.models import ForumTopicReadState

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
