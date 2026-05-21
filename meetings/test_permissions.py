from __future__ import annotations

from datetime import date

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.services.permission_bundles import sync_user_permission_bundles
from meetings.admin import MeetingAdmin
from meetings.models import Meeting


User = get_user_model()


class MeetingViewPermissionTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username="meeting-viewer", password="testpass123")
        self.uploader = User.objects.create_user(username="meeting-uploader", password="testpass123")
        self.uploader.user_permissions.add(Permission.objects.get(codename="add_meeting"))
        self.deleter = User.objects.create_user(username="meeting-deleter", password="testpass123")
        self.deleter.user_permissions.add(Permission.objects.get(codename="delete_meeting"))

        self.meeting = Meeting.objects.create(
            title="周例会",
            date=date(2026, 1, 3),
            file=SimpleUploadedFile("minutes.pdf", b"%PDF-1.4\nmeeting test", content_type="application/pdf"),
            uploaded_by=self.uploader,
        )
        self.addCleanup(self.meeting.file.delete, False)

    def test_meeting_list_requires_login(self):
        response = self.client.get(reverse("meetings:meeting_list"))

        self.assertEqual(response.status_code, 302)

    def test_meeting_detail_requires_login(self):
        response = self.client.get(reverse("meetings:meeting_detail", args=[self.meeting.pk]))

        self.assertEqual(response.status_code, 302)

    def test_meeting_pdf_preview_requires_login(self):
        response = self.client.get(reverse("meetings:meeting_pdf_inline", args=[self.meeting.pk]))

        self.assertEqual(response.status_code, 302)

    def test_logged_in_user_can_view_meeting_list_detail_and_pdf(self):
        self.client.force_login(self.viewer)

        list_response = self.client.get(reverse("meetings:meeting_list"))
        detail_response = self.client.get(reverse("meetings:meeting_detail", args=[self.meeting.pk]))
        pdf_response = self.client.get(reverse("meetings:meeting_pdf_inline", args=[self.meeting.pk]))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(pdf_response.status_code, 200)
        pdf_response.close()

    def test_meeting_upload_requires_add_permission(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("meetings:meeting_upload"))

        self.assertEqual(response.status_code, 403)

    def test_meeting_upload_business_bundle_grants_access(self):
        bundle_user = User.objects.create_user(username="meeting-bundle", password="testpass123")
        sync_user_permission_bundles(bundle_user, ["meetings.upload_meeting"])
        self.client.force_login(bundle_user)

        response = self.client.get(reverse("meetings:meeting_upload"))

        self.assertEqual(response.status_code, 200)

    def test_meeting_upload_sets_uploaded_by(self):
        self.client.force_login(self.uploader)

        response = self.client.post(
            reverse("meetings:meeting_upload"),
            data={
                "title": "晨会",
                "date": date(2026, 1, 4).isoformat(),
                "file": SimpleUploadedFile(
                    "morning.pdf",
                    b"%PDF-1.4\nmeeting upload test",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertEqual(response.status_code, 302)

        meeting = Meeting.objects.get(title="晨会")
        self.addCleanup(meeting.file.delete, False)
        self.assertEqual(meeting.uploaded_by, self.uploader)

    def test_meeting_delete_requires_delete_permission(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("meetings:meeting_delete", args=[self.meeting.pk]))

        self.assertEqual(response.status_code, 403)

    def test_meeting_delete_with_permission_removes_record(self):
        self.client.force_login(self.deleter)

        response = self.client.post(reverse("meetings:meeting_delete", args=[self.meeting.pk]), {"post": "yes"})

        self.assertRedirects(response, reverse("meetings:meeting_list"))
        self.assertFalse(Meeting.objects.filter(pk=self.meeting.pk).exists())


class MeetingAdminSaveModelTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="meeting-admin",
            email="meeting-admin@example.com",
            password="testpass123",
        )
        self.admin = MeetingAdmin(Meeting, AdminSite())
        self.factory = RequestFactory()

    def test_admin_save_model_sets_uploaded_by_on_create(self):
        meeting = Meeting(
            title="后台会议",
            date=date(2026, 1, 5),
            file=SimpleUploadedFile("admin.pdf", b"%PDF-1.4\nadmin meeting", content_type="application/pdf"),
        )

        request = self.factory.post("/admin/meetings/meeting/add/")
        request.user = self.admin_user

        self.admin.save_model(request, meeting, form=None, change=False)

        self.addCleanup(meeting.file.delete, False)
        meeting.refresh_from_db()
        self.assertEqual(meeting.uploaded_by, self.admin_user)