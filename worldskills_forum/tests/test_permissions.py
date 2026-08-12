from django.urls import reverse

from .base import ForumTestCase


class ForumPermissionTests(ForumTestCase):
    def topic_payload(self):
        return {
            "competition_year": 2026, "translated_title": "新主题", "original_title": "New Topic",
            "source_url": "https://forum.example.com/t/new", "source_topic_id": "", "summary": "",
            "module": self.module.pk, "category": self.category.pk, "tags_text": "Linux，评分", "status": "active", "importance": "normal",
        }

    def test_reader_can_read_but_cannot_create(self):
        post = self.make_post()
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse("worldskills_forum:feed")).status_code, 200)
        self.assertEqual(self.client.get(reverse("worldskills_forum:topic_detail", args=[post.topic_id])).status_code, 200)
        self.assertEqual(self.client.post(reverse("worldskills_forum:topic_create"), self.topic_payload()).status_code, 403)

    def test_translator_can_create_topic_with_new_tags_from_text_input(self):
        self.client.force_login(self.translator_a)
        response = self.client.post(reverse("worldskills_forum:topic_create"), self.topic_payload())
        self.assertEqual(response.status_code, 302)
        topic = self.translator_a.forum_topics_created.get(translated_title="新主题")
        self.assertEqual(set(topic.tags.values_list("name", flat=True)), {"Linux", "评分"})

    def test_topic_form_page_always_contains_editable_tag_control(self):
        self.tag.delete()
        self.client.force_login(self.translator_a)
        response = self.client.get(reverse("worldskills_forum:topic_create"))
        self.assertContains(response, 'name="tags_text"', html=False)
        self.assertContains(response, "直接输入标签")

    def test_topic_edit_page_prefills_and_can_replace_tags(self):
        topic = self.make_topic(user=self.translator_a)
        self.client.force_login(self.translator_a)
        edit_url = reverse("worldskills_forum:topic_edit", args=[topic.pk])

        response = self.client.get(edit_url)
        self.assertContains(response, 'name="tags_text"', html=False)
        self.assertContains(response, 'value="Linux"', html=False)

        payload = self.topic_payload()
        payload.update(
            {
                "translated_title": topic.translated_title,
                "original_title": topic.original_title,
                "source_url": topic.source_url,
                "tags_text": "评分",
            }
        )
        self.assertEqual(self.client.post(edit_url, payload).status_code, 302)
        self.assertEqual(list(topic.tags.values_list("name", flat=True)), ["评分"])

    def test_translator_can_edit_own_but_not_other_content(self):
        own = self.make_post(user=self.translator_a)
        other = self.make_post(user=self.translator_b, topic=self.make_topic(user=self.translator_b, source_url="https://forum.example.com/t/b"))
        self.client.force_login(self.translator_a)
        self.assertEqual(self.client.get(reverse("worldskills_forum:post_edit", args=[own.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("worldskills_forum:post_edit", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("worldskills_forum:post_delete", args=[own.pk])).status_code, 403)

    def test_empty_topic_is_hidden_and_owner_can_delete_it(self):
        empty = self.make_topic(user=self.translator_a)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse("worldskills_forum:topic_detail", args=[empty.pk])).status_code, 404)
        self.client.force_login(self.translator_a)
        self.assertEqual(self.client.post(reverse("worldskills_forum:topic_delete", args=[empty.pk])).status_code, 302)

    def test_manager_can_edit_and_delete_any_content(self):
        post = self.make_post(user=self.translator_a)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("worldskills_forum:post_edit", args=[post.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse("worldskills_forum:post_delete", args=[post.pk])).status_code, 302)
