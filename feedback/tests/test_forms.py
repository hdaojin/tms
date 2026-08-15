from feedback.forms import FeedbackForm, FeedbackManageForm, FeedbackReplyForm
from feedback.models import FeedbackCategory, FeedbackStatus

from .base import FeedbackTestCase


class FeedbackFormTests(FeedbackTestCase):
    def test_title_and_content_are_required(self):
        form = FeedbackForm(data={"category": FeedbackCategory.BUG, "title": " ", "content": " "})
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertIn("content", form.errors)

    def test_more_than_ten_attachments_is_rejected(self):
        files = [self.make_text(f"file-{index}.log") for index in range(11)]
        form = FeedbackForm(
            data={"category": FeedbackCategory.BUG, "title": "标题", "content": "正文"},
            files={"attachments": files},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("attachments", form.errors)

    def test_single_attachment_over_twenty_mb_is_rejected(self):
        large_file = self.make_text("large.log")
        large_file.size = 20 * 1024 * 1024 + 1
        form = FeedbackForm(
            data={"category": FeedbackCategory.BUG, "title": "标题", "content": "正文"},
            files={"attachments": [large_file]},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("attachments", form.errors)

    def test_total_attachment_size_over_fifty_mb_is_rejected(self):
        files = []
        for index in range(3):
            upload = self.make_text(f"large-{index}.log")
            upload.size = 17 * 1024 * 1024
            files.append(upload)
        form = FeedbackForm(
            data={"category": FeedbackCategory.BUG, "title": "标题", "content": "正文"},
            files={"attachments": files},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("attachments", form.errors)

    def test_disallowed_attachment_extension_is_rejected(self):
        form = FeedbackForm(
            data={"category": FeedbackCategory.BUG, "title": "标题", "content": "正文"},
            files={"attachments": [self.make_text("script.svg")]},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("attachments", form.errors)

    def test_complaint_is_not_forced_private_on_server(self):
        form = FeedbackForm(
            data={
                "category": FeedbackCategory.COMPLAINT,
                "title": "投诉",
                "content": "公开投诉",
                "is_private": "",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data["is_private"])

    def test_unbound_complaint_form_defaults_private(self):
        form = FeedbackForm(initial={"category": FeedbackCategory.COMPLAINT})
        self.assertTrue(form.fields["is_private"].initial)

    def test_create_form_does_not_expose_management_fields(self):
        self.assertNotIn("status", FeedbackForm().fields)
        self.assertNotIn("resolution", FeedbackForm().fields)
        self.assertNotIn("author", FeedbackForm().fields)

    def test_manage_form_requires_resolution_for_closed_feedback(self):
        form = FeedbackManageForm(data={"status": FeedbackStatus.CLOSED, "resolution": " "})
        self.assertFalse(form.is_valid())
        self.assertIn("resolution", form.errors)

    def test_reply_form_requires_content(self):
        form = FeedbackReplyForm(data={"content": " "})
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)
