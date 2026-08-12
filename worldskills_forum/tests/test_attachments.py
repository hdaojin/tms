import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse

from worldskills_forum.forms import AttachmentAddForm, validate_attachment_capacity
from worldskills_forum.models import ForumPostAttachment

from .base import ForumTestCase


class AttachmentTests(ForumTestCase):
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.override = override_settings(PRIVATE_MEDIA_ROOT=self.temp_dir.name)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.temp_dir.cleanup()
        super().tearDown()

    def test_extension_signature_and_count_validation(self):
        bad = SimpleUploadedFile("fake.pdf", b"not a pdf")
        form = AttachmentAddForm(data={"add-attachment_source_urls": ""}, files={"add-attachments": bad}, post=self.make_post(), prefix="add")
        self.assertFalse(form.is_valid())

    def test_total_size_is_enforced_without_allocating_large_files(self):
        fake_file = type("SizedFile", (), {"size": 101 * 1024 * 1024})()
        with self.assertRaises(ValidationError):
            validate_attachment_capacity(None, [fake_file])
        files = [SimpleUploadedFile(f"{index}.txt", b"x") for index in range(11)]
        form = AttachmentAddForm(data={"add-attachment_source_urls": ""}, files={"add-attachments": files}, post=self.make_post(), prefix="add")
        self.assertFalse(form.is_valid())

    def test_translator_can_submit_external_attachment(self):
        post = self.make_post(user=self.translator_a)
        self.client.force_login(self.translator_a)

        response = self.client.post(
            reverse("worldskills_forum:attachment_manage", args=[post.pk]),
            {
                "action": "add",
                "add-attachment_source_urls": "https://forum.example.com/files/guide.pdf",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(post.attachments.filter(source_url="https://forum.example.com/files/guide.pdf").exists())

    def test_private_inline_image_and_forced_attachment_download(self):
        post = self.make_post()
        image = ForumPostAttachment.objects.create(post=post, file=SimpleUploadedFile("shot.png", b"\x89PNG\r\n\x1a\nrest", content_type="image/png"), original_filename="shot.png", created_by=self.translator_a)
        pdf = ForumPostAttachment.objects.create(post=post, file=SimpleUploadedFile("guide.pdf", b"%PDF-1.7\n", content_type="application/pdf"), original_filename="guide.pdf", created_by=self.translator_a)
        self.client.force_login(self.reader)
        image_response = self.client.get(reverse("worldskills_forum:attachment_content", args=[image.pk]))
        pdf_response = self.client.get(reverse("worldskills_forum:attachment_content", args=[pdf.pk]))
        self.assertIn("inline", image_response["Content-Disposition"])
        self.assertIn("attachment", pdf_response["Content-Disposition"])
        self.assertEqual(image_response["X-Content-Type-Options"], "nosniff")
        image_response.close()
        pdf_response.close()

    def test_editing_display_name_cannot_turn_pdf_into_inline_image(self):
        post = self.make_post()
        attachment = ForumPostAttachment.objects.create(post=post, file=SimpleUploadedFile("guide.pdf", b"%PDF-1.7\n"), original_filename="guide.pdf", created_by=self.translator_a)
        attachment.original_filename = "renamed.png"
        attachment.save()
        self.assertFalse(attachment.is_safe_image)
        self.client.force_login(self.reader)
        response = self.client.get(reverse("worldskills_forum:attachment_content", args=[attachment.pk]))
        self.assertIn("attachment", response["Content-Disposition"])
        response.close()

    def test_external_image_is_not_hotlinked_and_xss_is_escaped(self):
        post = self.make_post()
        ForumPostAttachment.objects.create(post=post, source_url="https://outside.example/image.png", original_filename="image.png", kind="image", created_by=self.translator_a)
        post.translation.translated_content = "<script>alert(1)</script>"
        post.translation.save()
        self.client.force_login(self.reader)
        response = self.client.get(reverse("worldskills_forum:topic_detail", args=[post.topic_id]))
        self.assertNotContains(response, '<img src="https://outside.example/image.png"', html=False)
        self.assertNotContains(response, "<script>alert(1)</script>", html=False)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;", html=False)

    def test_delete_removes_private_file(self):
        post = self.make_post()
        attachment = ForumPostAttachment.objects.create(post=post, file=SimpleUploadedFile("guide.pdf", b"%PDF-1.7\n"), original_filename="guide.pdf", created_by=self.translator_a)
        stored_path = Path(attachment.file.path)
        self.assertTrue(stored_path.exists())
        attachment.delete()
        self.assertFalse(stored_path.exists())
