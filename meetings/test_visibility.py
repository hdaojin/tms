from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .admin import MeetingAdmin
from .forms import MeetingAudienceForm
from .models import Meeting
from .selectors import meeting_queryset_for
from .services import save_meeting

User = get_user_model()


class MeetingVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = cls.user("owner", "view", "add", "change", last_name="王", first_name="小明")
        cls.viewer = cls.user("viewer", "view", last_name="李", first_name="小红")
        cls.manager = cls.user("manager", "view", "change", "delete", is_staff=True)
        cls.other = cls.user("other", "view")
        cls.no_view = cls.user("no-view", "add", "change", "delete", is_staff=True)
        cls.superuser = cls.user("root", is_active=True, is_superuser=True, is_staff=True)
        cls.role = Group.objects.create(name="会议角色")
        cls.public = Meeting.objects.create(
            title="公开周例会", date=date(2026, 1, 3), file="public.pdf", uploaded_by=cls.owner
        )
        cls.secret = Meeting.objects.create(
            title="限定周例会", date=date(2026, 1, 4), file="secret.pdf", uploaded_by=cls.owner, is_public=False
        )
        cls.secret.visible_users.add(cls.viewer)

    @classmethod
    def user(cls, username, *permissions, **kwargs):
        user = User.objects.create_user(username=username, **kwargs)
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="meetings", codename__in=[f"{permission}_meeting" for permission in permissions]
            )
        )
        return user

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.settings_override = self.settings(PRIVATE_MEDIA_ROOT=temporary.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        storage = self.secret.file.storage
        storage.save("public.pdf", ContentFile(b"%PDF-1.4\npublic"))
        storage.save("secret.pdf", ContentFile(b"%PDF-1.4\nsecret"))

    def login(self, user):
        self.client.force_login(user)

    def test_all_read_routes_share_visibility_and_do_not_grant_permission(self):
        for user, allowed in (
            (self.owner, True),
            (self.viewer, True),
            (self.manager, False),
            (self.other, False),
            (self.no_view, False),
            (self.superuser, True),
        ):
            self.login(user)
            for route in ("meeting_detail", "meeting_pdf_inline", "meeting_file"):
                with self.subTest(user=user.username, route=route):
                    response = self.client.get(reverse(f"meetings:{route}", args=[self.secret.pk]))
                    self.assertEqual(response.status_code, 200 if allowed else 404)
                    response.close()
            if user != self.no_view:
                response = self.client.get(reverse("meetings:meeting_list"))
                self.assertEqual(response.context["table"].paginator.count, 2 if allowed else 1)
                if not allowed:
                    self.assertNotContains(response, self.secret.title)
        self.secret.visible_users.add(self.no_view)
        self.assertFalse(meeting_queryset_for(self.no_view).exists())
        self.viewer.is_active = False
        self.assertFalse(meeting_queryset_for(self.viewer).exists())

    def test_role_union_updates_immediately_without_duplicates(self):
        self.secret.visible_groups.add(self.role)
        self.role.user_set.add(self.other, self.viewer)
        self.assertEqual(meeting_queryset_for(self.other).filter(pk=self.secret.pk).count(), 1)
        self.assertEqual(meeting_queryset_for(self.viewer).filter(pk=self.secret.pk).count(), 1)
        self.role.user_set.remove(self.other)
        self.assertFalse(meeting_queryset_for(self.other).filter(pk=self.secret.pk).exists())
        self.role.delete()
        self.secret.refresh_from_db()
        self.assertFalse(self.secret.is_public)

    def test_permission_revocation_and_empty_audience_fail_closed(self):
        self.viewer.user_permissions.clear()
        self.assertFalse(meeting_queryset_for(User.objects.get(pk=self.viewer.pk)).exists())
        self.secret.visible_users.clear()
        self.assertFalse(meeting_queryset_for(self.other).filter(pk=self.secret.pk).exists())
        self.assertTrue(meeting_queryset_for(self.owner).filter(pk=self.secret.pk).exists())

    def test_deleting_last_selected_person_does_not_publish_record(self):
        self.viewer.delete()
        self.secret.refresh_from_db()
        self.assertFalse(self.secret.is_public)
        self.assertFalse(self.secret.visible_users.exists())
        self.assertFalse(meeting_queryset_for(self.other).filter(pk=self.secret.pk).exists())

    def test_nonvisible_change_delete_and_admin_cannot_bypass(self):
        self.login(self.manager)
        for method, route in (("get", "meeting_audience"), ("post", "meeting_audience"), ("post", "meeting_delete")):
            response = getattr(self.client, method)(reverse(f"meetings:{route}", args=[self.secret.pk]), {})
            self.assertEqual(response.status_code, 404)
        for suffix in ("change/", "delete/", "history/"):
            self.assertEqual(self.client.get(f"/admin/meetings/meeting/{self.secret.pk}/{suffix}").status_code, 404)
        request = RequestFactory().get("/admin/")
        request.user = self.manager
        admin = MeetingAdmin(Meeting, AdminSite())
        self.assertFalse(admin.get_queryset(request).filter(pk=self.secret.pk).exists())
        self.assertFalse(admin.has_change_permission(request, self.secret))

    def test_list_search_date_validation_and_htmx(self):
        self.login(self.viewer)
        url = reverse("meetings:meeting_list")
        for params, expected in (
            ({"q": "王小明"}, 2),
            ({"q": "secret.pdf"}, 1),
            ({"date_from": "2026-01-04", "date_to": "2026-01-04"}, 1),
            ({"q": "owner", "date_to": "2026-01-03"}, 1),
        ):
            response = self.client.get(url, params)
            self.assertEqual(response.context["table"].paginator.count, expected)
        for params in ({"date_from": "wrong"}, {"date_from": "2026-02-01", "date_to": "2026-01-01"}):
            response = self.client.get(url, params, HTTP_HX_REQUEST="true")
            self.assertTrue(response.context["filter_form"].errors)
            self.assertEqual(response.context["table"].paginator.count, 0)
            self.assertNotContains(response, "<!DOCTYPE")
            self.assertIn("HX-Request", response.headers["Vary"])
        self.assertEqual(self.client.get(url, {"sort": "uploaded_by"}).status_code, 200)
        self.login(self.other)
        self.assertEqual(self.client.get(url, {"q": self.secret.title}).context["table"].paginator.count, 0)

    def test_search_candidates_permissions_pagination_and_minimal_data(self):
        url = reverse("meetings:recipient_search")
        self.login(self.other)
        self.assertEqual(self.client.get(url, {"q": "王"}).status_code, 403)
        self.login(self.owner)
        self.assertEqual(self.client.get(url).json(), {"results": [], "has_more": False})
        result = self.client.get(url, {"q": "王小明"}).json()["results"]
        self.assertEqual(result, [{"id": self.owner.pk, "label": "王小明(owner)"}])
        for index in range(22):
            self.user(f"candidate-{index:02}", "view")
        self.user("candidate-no-permission")
        self.user("candidate-inactive", "view", is_active=False)
        first = self.client.get(url, {"q": "candidate"})
        second = self.client.get(url, {"q": "candidate", "page": 2}).json()
        self.assertEqual(len(first.json()["results"]), 20)
        self.assertTrue(first.json()["has_more"])
        self.assertEqual(len(second["results"]), 2)
        self.assertFalse(second["has_more"])
        self.assertEqual(first.headers["Cache-Control"], "private, no-store")
        self.assertEqual(self.client.get(url, {"q": "王", "page": "bad"}).status_code, 400)
        self.assertEqual(self.client.get(url, {"q": "王", "page": "9" * 100}).status_code, 400)
        self.login(self.manager)
        self.assertEqual(self.client.get(url, {"q": "王", "meeting_id": self.secret.pk}).status_code, 404)
        self.assertEqual(self.client.get(url, {"q": "王"}).status_code, 403)

    def test_settings_preserve_record_and_list_return_and_clear_public_selections(self):
        self.login(self.owner)
        original = (self.secret.title, self.secret.file.name, self.secret.uploaded_by_id, self.secret.uploaded_at)
        query = urlencode(
            {"q": "周例会", "date_from": "2026-01-01", "sort": "date", "page": "999", "next": "https://evil.invalid/"}
        )
        url = reverse("meetings:meeting_audience", args=[self.secret.pk]) + "?" + urlencode({"return_query": query})
        response = self.client.post(
            url, {"is_public": "on", "visible_users": [self.viewer.pk], "visible_groups": [self.role.pk]}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/meetings/?"))
        self.assertNotIn("evil", response.url)
        self.assertIn("page=1", response.url)
        self.secret.refresh_from_db()
        self.assertTrue(self.secret.is_public)
        self.assertFalse(self.secret.visible_users.exists())
        self.assertFalse(self.secret.visible_groups.exists())
        self.assertEqual(
            (self.secret.title, self.secret.file.name, self.secret.uploaded_by_id, self.secret.uploaded_at), original
        )

    def test_forms_reject_invalid_or_empty_targets_and_preserve_unavailable_existing_people(self):
        for data in (
            {},
            {"visible_users": [self.no_view.pk]},
            {"visible_groups": [999999]},
            {"visible_users": ["bad"]},
        ):
            form = MeetingAudienceForm(data=data, instance=self.secret)
            self.assertFalse(form.is_valid())
        self.viewer.is_active = False
        self.viewer.save(update_fields=["is_active"])
        form = MeetingAudienceForm(data={"visible_users": [self.viewer.pk]}, instance=self.secret)
        self.assertTrue(form.is_valid(), form.errors)
        html = str(form["visible_users"])
        self.assertIn("当前不可阅读", html)
        self.assertNotIn("manager", html)
        fresh = MeetingAudienceForm(data={"visible_users": [self.viewer.pk]})
        self.assertFalse(fresh.is_valid())

    def test_regular_readers_never_receive_specific_audience_names(self):
        self.secret.visible_groups.add(self.role)
        self.login(self.viewer)
        html = self.client.get(reverse("meetings:meeting_detail", args=[self.secret.pk]))
        self.assertContains(html, "限定人员可见")
        self.assertNotContains(html, self.role.name)
        self.assertNotContains(html, "李小红(viewer)")
        self.login(self.owner)
        html = self.client.get(reverse("meetings:meeting_detail", args=[self.secret.pk]))
        self.assertContains(html, self.role.name)
        self.assertContains(html, "李小红(viewer)")
        self.viewer.is_staff = True
        self.viewer.save(update_fields=["is_staff"])
        self.login(self.viewer)
        html = self.client.get(f"/admin/meetings/meeting/{self.secret.pk}/change/")
        self.assertEqual(html.status_code, 200)
        self.assertNotContains(html, self.role.name)
        self.assertNotContains(html, "李小红(viewer)")

    def test_upload_has_no_full_user_list_and_add_only_success_returns_to_upload(self):
        self.login(self.no_view)
        response = self.client.get(reverse("meetings:meeting_upload"))
        self.assertContains(response, "card-body")
        self.assertNotContains(response, "李小红")
        self.assertContains(response, 'data-audience-limited hidden')
        response = self.client.post(
            reverse("meetings:meeting_upload"),
            {
                "title": "新会议",
                "date": "2026-01-05",
                "is_public": "on",
                "file": SimpleUploadedFile("upload.pdf", b"%PDF-1.4\nnew"),
            },
        )
        self.assertRedirects(response, reverse("meetings:meeting_upload"))
        meeting = Meeting.objects.get(title="新会议")
        self.assertTrue(meeting.is_public)
        self.assertEqual(meeting.uploaded_by, self.no_view)

    def test_list_query_count_does_not_grow_with_rows_and_links_keep_filters(self):
        self.login(self.owner)
        url = reverse("meetings:meeting_list")
        # 预热模板和权限缓存；随后用同样请求比较列表增长前后的查询数。
        self.client.get(url)
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as first:
            self.client.get(url, {"q": "周例会"})
        for index in range(10):
            Meeting.objects.create(
                title=f"公开周例会{index}", date=date(2026, 1, 3), file="public.pdf", uploaded_by=self.owner
            )
        with CaptureQueriesContext(connection) as second:
            response = self.client.get(url, {"q": "周例会", "sort": "date"})
        self.assertLessEqual(len(second), len(first) + 1, "\n".join(query["sql"] for query in second.captured_queries))
        soup = BeautifulSoup(response.content, "html.parser")
        setting = soup.find("a", string=lambda text: text and text.strip() == "设置可见人员")
        self.assertIsNotNone(setting)
        self.assertIn("return_query=", setting["href"])
        self.assertIn("q%3D", setting["href"])

    def test_service_rolls_back_relations_and_rechecks_actor_scope(self):
        with self.assertRaises(Http404):
            save_meeting(
                meeting=self.secret,
                actor=self.manager,
                change=True,
                audience_only=True,
                is_public=True,
                group_ids=[],
                user_ids=[],
            )
        self.secret.refresh_from_db()
        self.assertFalse(self.secret.is_public)
        with patch.object(type(self.secret.visible_users), "set", side_effect=RuntimeError("rollback")):
            with self.assertRaises(RuntimeError):
                save_meeting(
                    meeting=self.secret,
                    actor=self.owner,
                    change=True,
                    audience_only=True,
                    is_public=False,
                    group_ids=[self.role.pk],
                    user_ids=[self.other.pk],
                )
        self.secret.refresh_from_db()
        self.assertEqual(list(self.secret.visible_users.all()), [self.viewer])
        self.assertFalse(self.secret.visible_groups.exists())

    def test_upload_rollback_cleans_only_new_file_and_replacement_rollback_keeps_original(self):
        meeting = Meeting(
            title="回滚会议", date=date(2026, 1, 5), file=SimpleUploadedFile("rollback.pdf", b"%PDF-1.4\nnew")
        )
        related_class = type(self.secret.visible_users)
        with patch.object(related_class, "set", side_effect=RuntimeError("rollback")):
            with self.assertRaises(RuntimeError):
                save_meeting(meeting=meeting, actor=self.owner, is_public=True, group_ids=[], user_ids=[])
        self.assertFalse(Meeting.objects.filter(title="回滚会议").exists())
        self.assertFalse(meeting.file.storage.exists(meeting.file.name))
        self.assertTrue(self.secret.file.storage.exists(self.secret.file.name))
        original = self.secret.file.name
        self.secret.file = SimpleUploadedFile("replace.pdf", b"%PDF-1.4\nreplacement")
        with patch.object(related_class, "set", side_effect=RuntimeError("rollback")):
            with self.assertRaises(RuntimeError):
                save_meeting(
                    meeting=self.secret, actor=self.owner, change=True, is_public=True, group_ids=[], user_ids=[]
                )
        self.secret.refresh_from_db()
        self.assertEqual(self.secret.file.name, original)
        self.assertTrue(self.secret.file.storage.exists(original))

    def test_delete_defers_file_cleanup_until_commit(self):
        name = self.secret.file.name
        storage = self.secret.file.storage
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                self.secret.delete()
                self.assertTrue(storage.exists(name))
        self.assertFalse(storage.exists(name))

    def test_service_rechecks_cached_actor_permission_and_candidate_eligibility(self):
        self.assertTrue(self.owner.has_perm("meetings.change_meeting"))
        self.owner.user_permissions.remove(
            Permission.objects.get(content_type__app_label="meetings", codename="change_meeting")
        )
        with self.assertRaises(PermissionDenied):
            save_meeting(
                meeting=self.secret,
                actor=self.owner,
                change=True,
                audience_only=True,
                is_public=True,
                group_ids=[],
                user_ids=[],
            )
        form = MeetingAudienceForm(data={"visible_users": [self.other.pk]}, instance=self.secret)
        self.assertTrue(form.is_valid(), form.errors)
        self.other.user_permissions.clear()
        with self.assertRaises(ValidationError):
            save_meeting(
                meeting=self.secret,
                actor=self.superuser,
                change=True,
                audience_only=True,
                is_public=False,
                group_ids=[],
                user_ids=[user.pk for user in form.cleaned_data["visible_users"]],
            )
        self.secret.refresh_from_db()
        self.assertFalse(self.secret.is_public)
        self.assertEqual(list(self.secret.visible_users.all()), [self.viewer])

    def test_admin_saves_audience_and_public_mode_clears_related_records(self):
        self.login(self.superuser)
        response = self.client.post(
            "/admin/meetings/meeting/add/",
            {
                "title": "后台上传",
                "date": "2026-01-05",
                "visible_users": [self.viewer.pk],
                "file": SimpleUploadedFile("admin.pdf", b"%PDF-1.4\nadmin"),
                "_save": "保存",
            },
        )
        self.assertEqual(response.status_code, 302)
        meeting = Meeting.objects.get(title="后台上传")
        self.assertFalse(meeting.is_public)
        self.assertEqual(list(meeting.visible_users.all()), [self.viewer])
        self.assertEqual(meeting.uploaded_by, self.superuser)
        response = self.client.post(
            f"/admin/meetings/meeting/{meeting.pk}/change/",
            {
                "title": meeting.title,
                "date": "2026-01-05",
                "is_public": "on",
                "visible_users": [self.viewer.pk],
                "visible_groups": [self.role.pk],
                "_save": "保存",
            },
        )
        self.assertEqual(response.status_code, 302)
        meeting.refresh_from_db()
        self.assertTrue(meeting.is_public)
        self.assertFalse(meeting.visible_users.exists())
        self.assertFalse(meeting.visible_groups.exists())

    def test_admin_later_failure_rolls_back_new_record_and_file(self):
        self.login(self.superuser)
        storage = self.secret.file.storage
        from pathlib import Path

        before = set(Path(storage.location).rglob("*.pdf"))
        with patch.object(MeetingAdmin, "log_addition", side_effect=RuntimeError("admin rollback")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    "/admin/meetings/meeting/add/",
                    {
                        "title": "后台回滚",
                        "date": "2026-01-05",
                        "is_public": "on",
                        "file": SimpleUploadedFile("admin-rollback.pdf", b"%PDF-1.4\nadmin"),
                        "_save": "保存",
                    },
                )
        self.assertFalse(Meeting.objects.filter(title="后台回滚").exists())
        self.assertEqual(set(Path(storage.location).rglob("*.pdf")), before)
