from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from django.utils import timezone

from worldskills_forum.forms import ForumPostTranslationForm, ForumTopicForm
from worldskills_forum.models import ForumPost, ForumPostAttachment, ForumSourceRole, ForumTag, ForumTopic, ForumTopicReadState

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

    def test_post_form_uses_editable_active_source_roles_and_keeps_current_inactive_role(self):
        custom_role = ForumSourceRole.objects.create(
            name="技术代表",
            slug="technical-delegate",
            sort_order=10,
        )
        topic = self.make_topic()
        create_form = ForumPostTranslationForm(topic=topic)
        self.assertIn(custom_role, create_form.fields["source_role"].queryset)

        post = self.make_post(topic=topic, source_role=custom_role)
        custom_role.is_active = False
        custom_role.save(update_fields=["is_active"])
        self.assertNotIn(
            custom_role,
            ForumPostTranslationForm(topic=post.topic).fields["source_role"].queryset,
        )
        self.assertIn(
            custom_role,
            ForumPostTranslationForm(post=post).fields["source_role"].queryset,
        )

    def test_source_role_controls_whether_detail_is_kept(self):
        detail_role = ForumSourceRole.objects.create(
            name="自定义身份",
            slug="custom-role",
            allows_detail=True,
        )
        post = self.make_post(
            source_role=detail_role,
            source_role_detail="区域技术顾问",
        )
        post.full_clean()
        self.assertEqual(post.source_role_detail, "区域技术顾问")

        post.source_role = self.expert_role
        post.full_clean()
        self.assertEqual(post.source_role_detail, "")

    def test_source_ids_are_validated_without_conditional_constraints(self):
        topic = self.make_topic(source_topic_id="topic-1")
        duplicate = ForumTopic(
            competition_year=2026,
            translated_title="重复来源主题",
            original_title="Duplicate source topic",
            source_url="https://forum.example.com/t/other",
            source_topic_id="topic-1",
            module=self.module,
            category=self.category,
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        self.make_post(topic=topic, source_post_id="post-1")
        duplicate_post = ForumPost(topic=topic, source_post_id="post-1")
        with self.assertRaises(ValidationError):
            duplicate_post.full_clean(exclude=["author_name", "source_role", "posted_at", "post_type", "original_content", "created_by", "updated_by"])

    def test_empty_source_ids_are_normalized_to_null_and_can_repeat(self):
        first = self.make_topic()
        second = self.make_topic(source_url="https://forum.example.com/t/other")
        self.assertIsNone(first.source_topic_id)
        self.assertIsNone(second.source_topic_id)

        first_post = self.make_post(topic=first)
        second_post = self.make_post(topic=first, source_url="https://forum.example.com/p/102")
        self.assertIsNone(first_post.source_post_id)
        self.assertIsNone(second_post.source_post_id)

        other_topic_post = self.make_post(topic=second, source_url="https://forum.example.com/p/103")
        first_post.source_post_id = "shared-post-id"
        first_post.save(update_fields=["source_post_id"])
        other_topic_post.source_post_id = "shared-post-id"
        other_topic_post.save(update_fields=["source_post_id"])

    def test_database_constraints_reject_duplicate_forum_sources(self):
        topic = self.make_topic(source_topic_id="topic-1")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ForumTopic.objects.create(
                    competition_year=2026,
                    translated_title="重复来源主题",
                    original_title="Duplicate source topic",
                    source_url="https://forum.example.com/t/duplicate",
                    source_topic_id="topic-1",
                    module=self.module,
                    category=self.category,
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ForumTopic.objects.create(
                    competition_year=2026,
                    translated_title="重复链接主题",
                    original_title="Duplicate source URL",
                    source_url=topic.source_url,
                    module=self.module,
                    category=self.category,
                )

        post = self.make_post(topic=topic, source_post_id="post-1")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ForumPost.objects.create(
                    topic=topic,
                    author_name="Expert B",
                    source_role=self.expert_role,
                    source_url="https://forum.example.com/p/duplicate",
                    source_post_id="post-1",
                    post_type="discussion",
                    importance="normal",
                    original_content="Duplicate post",
                )

        other_topic = self.make_topic(source_url="https://forum.example.com/t/other-topic")
        other_post = self.make_post(topic=other_topic, source_url="https://forum.example.com/p/other-topic", source_post_id="post-1")
        self.assertEqual(other_post.source_post_id, post.source_post_id)

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
