from feedback.models import FeedbackCategory
from feedback.permissions import (
    can_view_feedback,
    get_feedback_author_label,
    get_reply_author_label,
)
from feedback.selectors import filtered_feedbacks_for, visible_feedbacks_for

from .base import FeedbackTestCase


class FeedbackPermissionAndSelectorTests(FeedbackTestCase):
    def test_public_and_own_private_feedback_are_visible(self):
        public = self.make_feedback(title="公开")
        own_private = self.make_feedback(title="本人私密", is_private=True)
        other_private = self.make_feedback(title="他人私密", author=self.other, is_private=True)

        queryset = visible_feedbacks_for(self.author)
        self.assertEqual(set(queryset.values_list("pk", flat=True)), {public.pk, own_private.pk})
        self.assertNotIn(other_private.pk, queryset.values_list("pk", flat=True))

    def test_private_permission_sees_all_private_feedback(self):
        private = self.make_feedback(is_private=True)
        self.assertIn(private.pk, visible_feedbacks_for(self.private_viewer).values_list("pk", flat=True))

    def test_identity_permission_does_not_grant_private_access(self):
        private = self.make_feedback(is_private=True)
        self.assertFalse(can_view_feedback(self.identity_viewer, private))

    def test_search_and_filters_start_from_visible_scope(self):
        self.make_feedback(title="公开 Bug")
        self.make_feedback(title="私密 Bug", is_private=True, author=self.other)
        queryset = filtered_feedbacks_for(self.author, category=FeedbackCategory.BUG, query="Bug")
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().title, "公开 Bug")

    def test_anonymous_identity_and_reply_labels_are_separate(self):
        feedback = self.make_feedback(is_anonymous=True)
        self.assertEqual(get_feedback_author_label(self.other, feedback), "匿名用户")
        self.assertIn("张三", get_feedback_author_label(self.identity_viewer, feedback))
        self.assertEqual(get_reply_author_label(self.other, feedback, type("Reply", (), {"author_id": self.author.pk, "author": self.author})()), "匿名反馈人")
