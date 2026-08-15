from django.core.exceptions import ValidationError

from feedback.models import FeedbackAttachment, FeedbackReply, FeedbackStatus

from .base import FeedbackTestCase


class FeedbackModelTests(FeedbackTestCase):
    def test_default_status_is_open(self):
        feedback = self.make_feedback()
        self.assertEqual(feedback.status, FeedbackStatus.OPEN)

    def test_resolved_or_closed_requires_resolution(self):
        feedback = self.make_feedback(status=FeedbackStatus.RESOLVED)
        with self.assertRaises(ValidationError):
            feedback.full_clean()

    def test_attachment_reply_must_belong_to_same_feedback(self):
        first = self.make_feedback(title="第一条")
        second = self.make_feedback(title="第二条")
        reply = FeedbackReply.objects.create(feedback=first, author=self.author, content="补充")
        attachment = FeedbackAttachment(
            feedback=second,
            reply=reply,
            file=self.make_text(),
            original_filename="details.log",
            file_size=3,
            uploaded_by=self.author,
        )
        with self.assertRaises(ValidationError):
            attachment.full_clean()

    def test_attachment_filename_is_sanitized_and_file_is_cleaned_up(self):
        feedback = self.make_feedback()
        attachment = FeedbackAttachment(
            feedback=feedback,
            file=self.make_text("..\\logs/error.log"),
            original_filename="..\\logs/error.log",
            file_size=3,
            uploaded_by=self.author,
        )
        attachment.full_clean()
        attachment.save()
        self.assertNotIn("/", attachment.original_filename)
        self.assertNotIn("\\", attachment.original_filename)
        stored_name = attachment.file.name
        storage = attachment.file.storage
        self.assertTrue(storage.exists(stored_name))

        attachment.delete()
        self.assertFalse(storage.exists(stored_name))
