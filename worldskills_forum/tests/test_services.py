import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from worldskills_forum.models import ForumPost
from worldskills_forum.services import create_published_post, update_published_post

from .base import ForumTestCase


class ForumServiceTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(PRIVATE_MEDIA_ROOT=self.temp_dir.name)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.temp_dir.cleanup()
        super().tearDown()

    def post_data(self):
        return {
            "author_name": "WorldSkills Secretariat", "source_role": "worldskills_official",
            "source_role_detail": "", "posted_at": timezone.now(), "source_url": "https://forum.example.com/p/1",
            "source_post_id": "p-1", "post_type": "official_reply", "importance": "important",
            "original_content": "Official reply",
        }

    def test_create_is_atomic_and_sets_publish_ownership(self):
        topic = self.make_topic()
        post = create_published_post(topic=topic, post_data=self.post_data(), translation_data={"translated_content": "官方回复"}, user=self.translator_a)
        self.assertEqual(post.created_by, self.translator_a)
        self.assertEqual(post.translation.translated_by, self.translator_a)
        self.assertIsNotNone(post.translation.published_at)

    def test_translation_failure_rolls_back_post(self):
        topic = self.make_topic()
        with patch("worldskills_forum.services.ForumTranslation.save", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                create_published_post(topic=topic, post_data=self.post_data(), translation_data={"translated_content": "译文"}, user=self.translator_a)
        self.assertFalse(ForumPost.objects.filter(topic=topic).exists())

    def test_update_preserves_publisher_and_published_at(self):
        post = self.make_post()
        publisher = post.translation.translated_by
        published_at = post.translation.published_at
        data = self.post_data()
        data["source_post_id"] = ""
        update_published_post(post=post, post_data=data, translation_data={"translated_content": "更新译文"}, user=self.manager)
        post.refresh_from_db()
        self.assertEqual(post.translation.translated_by, publisher)
        self.assertEqual(post.translation.published_at, published_at)
        self.assertEqual(post.translation.updated_by, self.manager)

    def test_create_accepts_local_and_url_only_attachments(self):
        topic = self.make_topic()
        upload = SimpleUploadedFile("guide.pdf", b"%PDF-1.7\n", content_type="application/pdf")
        post = create_published_post(
            topic=topic, post_data=self.post_data(), translation_data={"translated_content": "译文"}, user=self.translator_a,
            uploaded_attachments=[upload], external_attachment_urls=["https://forum.example.com/files/image.png"],
        )
        self.assertEqual(post.attachments.count(), 2)
        self.assertEqual(post.attachments.get(source_url__contains="image.png").kind, "image")
