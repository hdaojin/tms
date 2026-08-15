from django.urls import reverse

from feedback.models import FeedbackStatus

from .base import FeedbackTestCase


class FeedbackViewTests(FeedbackTestCase):
    def test_create_form_explains_form_wide_screenshot_paste(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse("feedback:create"))
        self.assertContains(response, "复制截图后直接按 Ctrl+V / Cmd+V 即可添加，无需点击此处")
        self.assertNotContains(response, 'x-on:paste="handlePaste"', html=False)

    def test_list_create_and_detail_are_available_to_logged_in_users(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(reverse("feedback:list")).status_code, 200)
        create_response = self.client.post(
            reverse("feedback:create"),
            {"category": "bug", "title": "新反馈", "content": "正文"},
        )
        self.assertEqual(create_response.status_code, 302)
        feedback = self.author.feedbacks_created.get(title="新反馈")
        self.assertEqual(self.client.get(reverse("feedback:detail", args=[feedback.pk])).status_code, 200)

    def test_private_feedback_returns_404_to_unauthorized_user(self):
        feedback = self.make_feedback(is_private=True, author=self.other)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(reverse("feedback:detail", args=[feedback.pk])).status_code, 404)
        self.client.force_login(self.private_viewer)
        self.assertEqual(self.client.get(reverse("feedback:detail", args=[feedback.pk])).status_code, 200)

    def test_attachment_view_is_controlled_and_returns_expected_disposition(self):
        feedback = self.make_feedback()
        image = feedback.attachments.create(
            file=self.make_png(),
            original_filename="screen.png",
            file_size=13,
            uploaded_by=self.author,
        )
        document = feedback.attachments.create(
            file=self.make_pdf(),
            original_filename="details.pdf",
            file_size=12,
            uploaded_by=self.author,
        )
        self.client.force_login(self.author)
        image_response = self.client.get(reverse("feedback:attachment", args=[image.pk]))
        document_response = self.client.get(reverse("feedback:attachment", args=[document.pk]))
        self.assertEqual(image_response.status_code, 200)
        self.assertIn("inline", image_response["Content-Disposition"])
        self.assertIn("attachment", document_response["Content-Disposition"])
        self.assertEqual(image_response["X-Content-Type-Options"], "nosniff")
        image_response.close()
        document_response.close()

    def test_private_attachment_returns_404_to_unauthorized_user(self):
        feedback = self.make_feedback(is_private=True, author=self.other)
        attachment = feedback.attachments.create(
            file=self.make_text(),
            original_filename="details.log",
            file_size=3,
            uploaded_by=self.other,
        )
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(reverse("feedback:attachment", args=[attachment.pk])).status_code, 404)

    def test_anonymous_author_is_not_leaked_in_html(self):
        feedback = self.make_feedback(is_anonymous=True)
        self.client.force_login(self.other)
        response = self.client.get(reverse("feedback:detail", args=[feedback.pk]))
        content = response.content.decode()
        self.assertContains(response, "匿名用户")
        self.assertNotIn(self.author.username, content)
        self.assertNotIn("张三", content)

    def test_multipart_create_and_reply(self):
        self.client.force_login(self.author)
        create_response = self.client.post(
            reverse("feedback:create"),
            {"category": "bug", "title": "带截图", "content": "正文", "attachments": [self.make_png()]},
        )
        feedback = self.author.feedbacks_created.get(title="带截图")
        self.assertEqual(create_response.status_code, 302)
        reply_response = self.client.post(
            reverse("feedback:reply", args=[feedback.pk]),
            {"content": "回复", "attachments": [self.make_text("reply.log")]},
        )
        self.assertEqual(reply_response.status_code, 302)
        self.assertEqual(feedback.replies.count(), 1)

    def test_closed_feedback_hides_reply_form_for_normal_user(self):
        feedback = self.make_feedback(status=FeedbackStatus.CLOSED, resolution="已关闭")
        self.client.force_login(self.author)
        response = self.client.get(reverse("feedback:detail", args=[feedback.pk]))
        self.assertNotContains(response, f'action="{reverse("feedback:reply", args=[feedback.pk])}"', html=False)

    def test_reply_form_explains_form_wide_screenshot_paste(self):
        feedback = self.make_feedback()
        self.client.force_login(self.author)
        response = self.client.get(reverse("feedback:detail", args=[feedback.pk]))
        self.assertContains(response, "复制截图后直接按 Ctrl+V / Cmd+V 即可添加，无需点击此处")
        self.assertNotContains(response, 'x-on:paste="handlePaste"', html=False)

    def test_manager_can_update_status_and_detail_shows_resolution(self):
        feedback = self.make_feedback()
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("feedback:manage", args=[feedback.pk]),
            {"status": FeedbackStatus.RESOLVED, "resolution": "已经修复"},
        )
        self.assertEqual(response.status_code, 302)
        detail_response = self.client.get(reverse("feedback:detail", args=[feedback.pk]))
        self.assertContains(detail_response, "已经修复")
        self.assertContains(detail_response, "处理人：manager")

    def test_closed_feedback_rejects_normal_user_reply(self):
        feedback = self.make_feedback(status=FeedbackStatus.CLOSED, resolution="已关闭")
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("feedback:reply", args=[feedback.pk]),
            {"content": "不应成功"},
        )
        self.assertEqual(response.status_code, 403)

    def test_htmx_list_returns_only_list_fragment(self):
        self.make_feedback()
        self.client.force_login(self.author)
        response = self.client.get(reverse("feedback:list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<!doctype html>", html=False)
        self.assertContains(response, "测试反馈")
