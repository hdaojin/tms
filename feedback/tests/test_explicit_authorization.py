from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from feedback.models import Feedback, FeedbackAttachment
from feedback.permissions import can_view_feedback
from feedback.selectors import visible_feedbacks_for
from feedback.services import add_feedback_reply, create_feedback

from .base import FeedbackTestCase


class ExplicitFeedbackAuthorizationTests(FeedbackTestCase):
    def setUp(self):
        super().setUp()
        self.unassigned = get_user_model().objects.create_user("unassigned-feedback")
        self.feedback = self.make_feedback()

    def test_no_business_permission_means_no_entry_or_mutation_or_attachment(self):
        attachment = FeedbackAttachment.objects.create(
            feedback=self.feedback,
            file=self.make_pdf("unread.pdf"),
            original_filename="unread.pdf",
            file_size=1,
            uploaded_by=self.author,
        )
        self.client.force_login(self.unassigned)
        for name, args in (
            ("list", []),
            ("create", []),
            ("detail", [self.feedback.pk]),
            ("manage", [self.feedback.pk]),
            ("attachment", [attachment.pk]),
        ):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(f"feedback:{name}", args=args)).status_code, 403)
        for name, args, data in (
            ("create", [], {"category": "bug", "title": "forged", "content": "正文"}),
            ("reply", [self.feedback.pk], {"content": "forged"}),
        ):
            self.assertEqual(self.client.post(reverse(f"feedback:{name}", args=args), data).status_code, 403)
        self.assertFalse(Feedback.objects.filter(title="forged").exists())
        self.assertFalse(self.feedback.replies.exists())
        self.assertFalse(visible_feedbacks_for(self.unassigned).exists())
        self.assertFalse(can_view_feedback(self.unassigned, self.feedback))
        with self.assertRaises(PermissionDenied):
            create_feedback(
                data={"category": self.feedback.category, "title": "forged", "content": "正文"}, actor=self.unassigned
            )
        with self.assertRaises(PermissionDenied):
            add_feedback_reply(feedback=self.feedback, content="forged", actor=self.unassigned)
        home = self.client.get(reverse("accounts:home"))
        self.assertEqual(home.status_code, 200)
        self.assertNotContains(home, reverse("feedback:list"))
        self.assertNotContains(home, reverse("feedback:create"))

    def test_readonly_does_not_show_submit_reply_or_attachment_controls(self):
        self.grant(self.unassigned, "view_feedback")
        self.client.force_login(self.unassigned)
        listing = self.client.get(reverse("feedback:list"))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.context["page_actions"], [])
        self.assertNotContains(self.client.get(reverse("feedback:detail", args=[self.feedback.pk])), "提交回复")
        self.assertEqual(self.client.get(reverse("feedback:create")).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("feedback:reply", args=[self.feedback.pk]), {"content": "reply"}).status_code, 403
        )

    def test_create_and_reply_without_upload_permission_cannot_write_files(self):
        self.grant(self.unassigned, "view_feedback", "add_feedback", "add_feedbackreply")
        self.client.force_login(self.unassigned)
        response = self.client.get(reverse("feedback:create"))
        self.assertNotContains(response, 'name="attachments"')
        with self.assertRaises(PermissionDenied):
            create_feedback(
                data={"category": self.feedback.category, "title": "with-file", "content": "正文"},
                attachments=[self.make_pdf()],
                actor=self.unassigned,
            )
        self.assertFalse(Feedback.objects.filter(title="with-file").exists())
        self.assertFalse(list(Path(self.private_media.name).rglob("*.pdf")))
