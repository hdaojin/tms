from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError

from django.utils import timezone

from worldskills_forum.forms import ForumPostTranslationForm, ForumTopicForm
from worldskills_forum.models import ForumPost, ForumPostAttachment, ForumTag, ForumTopicReadState

from .base import ForumTestCase


class ForumModelTests(ForumTestCase):
    def test_posted_at_defaults_to_current_time_in_model_and_form(self):
        before = timezone.now()
        post = ForumPost(topic=self.make_topic())
        after = timezone.now()
        self.assertLessEqual(before, post.posted_at)
        self.assertLessEqual(post.posted_at, after)
        form = ForumPostTranslationForm(topic=post.topic)
        self.assertTrue(form.fields["posted_at"].initial)

    def test_topic_form_can_replace_tags_and_keeps_inactive_taxonomy_editable(self):
        topic = self.make_topic()
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])
        self.module.is_active = False
        self.module.save(update_fields=["is_active"])
        form = ForumTopicForm(
            data={
                "competition_year": topic.competition_year,
                "translated_title": topic.translated_title,
                "original_title": topic.original_title,
                "source_url": topic.source_url,
                "source_topic_id": "",
                "summary": "",
                "module": self.module.pk,
                "category": self.category.pk,
                "tags_text": "评分；竞赛规则，评分",
                "status": topic.status,
                "importance": topic.importance,
            },
            instance=topic,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(
            set(topic.tags.values_list("name", flat=True)),
            {"评分", "竞赛规则"},
        )
        self.assertFalse(topic.tags.filter(name="Linux").exists())

        edit_form = ForumTopicForm(instance=topic)
        self.assertEqual(
            set(edit_form.fields["tags_text"].initial.split("，")),
            {"评分", "竞赛规则"},
        )

    def test_topic_form_renders_editable_tag_input_when_no_tags_exist(self):
        ForumTag.objects.all().delete()
        form = ForumTopicForm()
        rendered = form["tags_text"].as_widget()
        self.assertIn('name="tags_text"', rendered)
        self.assertIn("例如：Linux，评分，竞赛规则", rendered)

    def test_topic_post_translation_and_timeline_order(self):
        topic = self.make_topic()
        later = self.make_post(topic=topic, source_url="https://forum.example.com/p/2")
        earlier = self.make_post(topic=topic, posted_at=later.posted_at.replace(year=2025), source_url="https://forum.example.com/p/1")
        self.assertEqual(list(topic.posts.values_list("pk", flat=True)), [earlier.pk, later.pk])
        self.assertEqual(later.translation.post, later)

    def test_source_ids_are_validated_without_conditional_constraints(self):
        topic = self.make_topic(source_topic_id="topic-1")
        duplicate = self.make_topic(source_url="https://forum.example.com/t/other", source_topic_id="topic-1")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        self.make_post(topic=topic, source_post_id="post-1")
        duplicate_post = ForumPost(topic=topic, source_post_id="post-1")
        with self.assertRaises(ValidationError):
            duplicate_post.full_clean(exclude=["author_name", "source_role", "posted_at", "post_type", "original_content", "created_by", "updated_by"])

    def test_category_is_protected_and_read_state_is_unique(self):
        topic = self.make_topic()
        with self.assertRaises(ProtectedError):
            self.category.delete()
        ForumTopicReadState.objects.create(user=self.reader, topic=topic, last_viewed_at=topic.created_at)
        with self.assertRaises(ValidationError):
            ForumTopicReadState(user=self.reader, topic=topic, last_viewed_at=topic.created_at).validate_constraints()

    def test_attachment_requires_file_or_http_source(self):
        post = self.make_post()
        with self.assertRaises(ValidationError):
            ForumPostAttachment(post=post, original_filename="missing").full_clean()
        with self.assertRaises(ValidationError):
            ForumPostAttachment(post=post, original_filename="ftp", source_url="ftp://example.com/a.pdf").full_clean()
