import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.bootstrap_engine import bootstrap_defaults
from feedback.models import Feedback, FeedbackCategory


BUG_CODE = 'bug'
FEATURE_CODE = 'feature'
COMPLAINT_CODE = 'complaint'


class FeedbackTestCase(TestCase):
    def setUp(self):
        bootstrap_defaults()
        self.private_media = tempfile.TemporaryDirectory()
        self.private_media_override = override_settings(PRIVATE_MEDIA_ROOT=self.private_media.name)
        self.private_media_override.enable()

        user_model = get_user_model()
        self.author = user_model.objects.create_user(
            username="real-author-unique",
            password="test",
            first_name="三",
            last_name="张",
        )
        self.other = user_model.objects.create_user(username="other", password="test")
        self.manager = user_model.objects.create_user(username="manager", password="test")
        self.private_viewer = user_model.objects.create_user(username="private-viewer", password="test")
        self.identity_viewer = user_model.objects.create_user(username="identity-viewer", password="test")
        self.grant(self.manager, "manage_feedback", "view_private_feedback")
        self.grant(self.private_viewer, "view_private_feedback")
        self.grant(self.identity_viewer, "view_anonymous_identity")

    def tearDown(self):
        self.private_media_override.disable()
        self.private_media.cleanup()
        super().tearDown()

    def grant(self, user, *codenames):
        user.user_permissions.add(
            *Permission.objects.filter(content_type__app_label="feedback", codename__in=codenames)
        )

    def make_feedback(self, author=None, **kwargs):
        data = {
            "category": FeedbackCategory.objects.get(code=BUG_CODE),
            "title": "测试反馈",
            "content": "反馈正文内容",
            "author": author or self.author,
        }
        data.update(kwargs)
        if isinstance(data['category'], str):
            data['category'] = FeedbackCategory.objects.get(code=data['category'])
        return Feedback.objects.create(**data)

    @staticmethod
    def make_png(name="screen.png"):
        return SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\nimage", content_type="image/png")

    @staticmethod
    def make_pdf(name="details.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.7\nfile", content_type="application/pdf")

    @staticmethod
    def make_text(name="details.log", content=b"log"):
        return SimpleUploadedFile(name, content, content_type="text/plain")
