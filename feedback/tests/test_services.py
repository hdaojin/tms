from django.core.exceptions import PermissionDenied, ValidationError

from feedback.models import FeedbackCategory, FeedbackReply, FeedbackStatus
from feedback.services import add_feedback_reply, create_feedback, update_feedback_status

from .base import FeedbackTestCase


class FeedbackServiceTests(FeedbackTestCase):
    def test_create_feedback_with_attachments(self):
        feedback = create_feedback(
            data={
                "category": FeedbackCategory.objects.get(code='bug'),
                "title": "导入异常",
                "content": "提交截图",
                "is_anonymous": True,
                "is_private": True,
            },
            attachments=[self.make_png(), self.make_text()],
            actor=self.author,
        )
        self.assertEqual(feedback.author, self.author)
        self.assertEqual(feedback.attachments.count(), 2)
        self.assertTrue(feedback.is_private)

    def test_reply_updates_feedback_activity_and_accepts_attachments(self):
        feedback = self.make_feedback()
        old_updated_at = feedback.updated_at
        reply = add_feedback_reply(
            feedback=feedback,
            content="补充信息",
            attachments=[self.make_png("reply.png")],
            actor=self.author,
        )
        self.assertIsInstance(reply, FeedbackReply)
        feedback.refresh_from_db()
        self.assertGreaterEqual(feedback.updated_at, old_updated_at)
        self.assertEqual(reply.attachments.count(), 1)

    def test_closed_feedback_rejects_normal_user_but_manager_can_reply(self):
        feedback = self.make_feedback(status=FeedbackStatus.CLOSED, resolution="已处理")
        with self.assertRaises(PermissionDenied):
            add_feedback_reply(feedback=feedback, content="普通用户回复", actor=self.author)
        reply = add_feedback_reply(feedback=feedback, content="工作人员补充", actor=self.manager)
        self.assertEqual(reply.author, self.manager)

    def test_manager_status_update_sets_and_clears_resolution_metadata(self):
        feedback = self.make_feedback()
        update_feedback_status(
            feedback=feedback,
            status=FeedbackStatus.RESOLVED,
            resolution="问题已修复",
            actor=self.manager,
        )
        feedback.refresh_from_db()
        self.assertEqual(feedback.status, FeedbackStatus.RESOLVED)
        self.assertEqual(feedback.resolved_by, self.manager)
        self.assertIsNotNone(feedback.resolved_at)

        update_feedback_status(
            feedback=feedback,
            status=FeedbackStatus.OPEN,
            resolution=feedback.resolution,
            actor=self.manager,
        )
        feedback.refresh_from_db()
        self.assertEqual(feedback.status, FeedbackStatus.OPEN)
        self.assertIsNone(feedback.resolved_by)
        self.assertIsNone(feedback.resolved_at)
        self.assertEqual(feedback.resolution, "问题已修复")

    def test_non_manager_cannot_update_status(self):
        feedback = self.make_feedback()
        with self.assertRaises(PermissionDenied):
            update_feedback_status(
                feedback=feedback,
                status=FeedbackStatus.IN_PROGRESS,
                resolution="",
                actor=self.author,
            )

    def test_resolved_status_without_resolution_is_rejected(self):
        feedback = self.make_feedback()
        with self.assertRaises(ValidationError):
            update_feedback_status(
                feedback=feedback,
                status=FeedbackStatus.RESOLVED,
                resolution="",
                actor=self.manager,
            )
