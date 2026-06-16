from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import django_tables2 as tables
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db.migrations.writer import MigrationWriter
from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse

from accounts.services.permission_bundles import sync_user_permission_bundles
from behaviors.models import ConductSummary
from core.forms.fields import MultipleFileField
from core.uploads import (
    ASSESSMENT_TP_UPLOAD_SPEC,
    COMPETITION_DOCUMENT_UPLOAD_SPEC,
    CONDUCT_ATTACHMENT_UPLOAD_SPEC,
    MEETING_FILE_UPLOAD_SPEC,
    NOTICE_ATTACHMENT_UPLOAD_SPEC,
    TRAININGLOG_UPLOAD_SPEC,
    FileUploadMixin,
    PrivateMediaStorage,
    UploadSignatureValidator,
    UploadSizeValidator,
    UploadSpec,
    format_file_size,
    get_file_icon_class,
    is_image_file,
    validate_upload_file,
)
from core.utils.tables import ActionsColumn, BaseTable
from core.utils.admin_deletion import discard_registered_delete_permissions, register_delete_permission_exemptions


User = get_user_model()
PDF_BYTES = b"%PDF-1.7\n% test pdf\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
ZIP_BYTES = b"PK\x03\x04" + b"\x00" * 16
JSON_BYTES = b'{"ok": true}'


class DeletePermissionExemptionRegistryTests(TestCase):
    def test_registered_source_model_discards_registered_target_permission(self):
        register_delete_permission_exemptions(
            "auth.User",
            ["behaviors.ConductSummary"],
        )
        user = User(username="registry-user")
        perms_needed = {str(ConductSummary._meta.verbose_name), "其他模型"}

        discard_registered_delete_permissions([user], perms_needed)

        self.assertSetEqual(perms_needed, {"其他模型"})

    def test_unregistered_source_model_keeps_permission_set_unchanged(self):
        group = Group(name="registry-group")
        perms_needed = {str(ConductSummary._meta.verbose_name)}

        discard_registered_delete_permissions([group], perms_needed)

        self.assertSetEqual(perms_needed, {str(ConductSummary._meta.verbose_name)})


class SiteRobotsDirectiveTests(TestCase):
    """站点应通过 robots.txt 与 meta 指令禁止搜索引擎收录。"""

    def test_robots_txt_is_public_and_blocks_all_crawlers(self):
        response = self.client.get(reverse("robots_txt"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        self.assertContains(response, "User-agent: *")
        self.assertContains(response, "Disallow: /")

    def test_homepage_includes_noindex_meta_tags(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<meta name="robots" content="noindex, nofollow" />',
            html=True,
        )
        self.assertContains(
            response,
            '<meta name="googlebot" content="noindex, nofollow" />',
            html=True,
        )


class MobileNavigationTemplateTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_render_mobile_navigation_shows_current_section_and_permitted_nested_items(self):
        user = User.objects.create_user(username="mobile-nav-user", password="testpass123")
        sync_user_permission_bundles(user, ["competitions.create_skillposition"])

        request = self.factory.get(reverse("competitions:skillposition_create"))
        request.user = user
        request.resolver_match = resolve(request.path)

        html = Template("{% load menu_tags %}{% render_mobile_navigation %}").render(
            Context({"request": request})
        )

        self.assertIn("当前位于“竞赛”", html)
        self.assertIn("竞赛信息", html)
        self.assertIn("新增岗位人员", html)
        self.assertNotIn("新增专家", html)

    def test_render_mobile_navigation_hides_notice_create_without_permission(self):
        user = User.objects.create_user(username="notice-nav-user", password="testpass123")

        request = self.factory.get(reverse("notices:notice_list"))
        request.user = user
        request.resolver_match = resolve(request.path)

        html = Template("{% load menu_tags %}{% render_mobile_navigation %}").render(
            Context({"request": request})
        )

        self.assertIn("通知公告列表", html)
        self.assertNotIn("创建通知公告", html)

    def test_render_mobile_navigation_shows_notice_create_with_publish_bundle(self):
        user = User.objects.create_user(username="notice-nav-editor", password="testpass123")
        sync_user_permission_bundles(user, ["notices.publish_notice"])
        user = User.objects.get(pk=user.pk)

        request = self.factory.get(reverse("notices:notice_list"))
        request.user = user
        request.resolver_match = resolve(request.path)

        html = Template("{% load menu_tags %}{% render_mobile_navigation %}").render(
            Context({"request": request})
        )

        self.assertIn("创建通知公告", html)

    def test_authenticated_page_header_includes_mobile_navigation_trigger_and_panel(self):
        user = User.objects.create_user(username="mobile-nav-header", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-mobile-nav-trigger")
        self.assertContains(response, "data-mobile-nav-panel")

    def test_authenticated_page_keeps_horizontal_overflow_on_body_not_header(self):
        user = User.objects.create_user(username="mobile-nav-overflow", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'body class="flex min-h-screen flex-col overflow-x-hidden"')
        self.assertNotContains(
            response,
            'class="navbar sticky top-0 z-20 w-full max-w-full overflow-x-hidden',
        )


class ResponsiveTableTemplateTests(TestCase):
    def test_render_table_wraps_table_in_horizontal_scroll_container(self):
        class DemoTable(BaseTable):
            name = tables.Column(verbose_name="名称")

            class Meta(BaseTable.Meta):
                pass

        table = DemoTable([{"name": "示例数据"}])
        request = RequestFactory().get(reverse("home"))

        html = Template("{% load django_tables2 %}{% render_table table %}").render(
            Context({"table": table, "request": request})
        )

        self.assertIn('class="table-container w-full max-w-full overflow-x-auto"', html)


class ActionsColumnRenderingTests(TestCase):
    @patch("core.utils.tables.get_token", return_value="csrf-token")
    @patch("core.utils.tables.reverse")
    def test_actions_column_renders_nowrap_buttons_with_mobile_gap(self, mock_reverse, _mock_token):
        mock_reverse.side_effect = lambda name, args: f"/{name}/{args[0]}/"

        class DummyMeta:
            app_label = "core"
            model_name = "dummy"

        record = SimpleNamespace(pk=7, _meta=DummyMeta())
        user = User.objects.create_user(username="actions-user", password="testpass123")
        table = SimpleNamespace(request=SimpleNamespace(user=user))
        column = ActionsColumn(view_url="core:view", edit_url="core:edit", delete_url="core:delete")

        html = column.render(None, record=record, table=table)

        self.assertIn("flex flex-col items-center gap-2 sm:flex-row sm:flex-wrap sm:justify-center", html)
        self.assertIn("btn btn-soft btn-primary btn-xs whitespace-nowrap", html)
        self.assertIn("btn btn-soft btn-warning btn-xs whitespace-nowrap", html)
        self.assertIn("btn btn-soft btn-error btn-xs whitespace-nowrap", html)


class InternalCutoverOrchestratorCommandTests(TestCase):
    def test_reconcile_internal_app_cutovers_is_noop_for_current_state(self):
        output = StringIO()

        call_command("reconcile_internal_app_cutovers", stdout=output)

        value = output.getvalue()
        self.assertIn("cutover_assessment_to_assessments", value)
        self.assertIn("当前数据库与文件目录已经使用 assessments，无需切换。", value)
        self.assertIn("当前数据库与文件目录已经使用 behaviors，无需切换。", value)
        self.assertIn("当前数据库与文件目录已经使用 meetings，无需切换。", value)
        self.assertIn("以上为统一预检查结果。确认无误后，请追加 --execute 执行实际收尾。", value)

    @patch("core.management.commands.reconcile_internal_app_cutovers.subprocess.run")
    def test_reconcile_internal_app_cutovers_runs_migrate_in_fresh_process(self, mock_run):
        output = StringIO()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "No migrations to apply.\n"
        mock_run.return_value.stderr = ""

        call_command("reconcile_internal_app_cutovers", execute=True, stdout=output)

        mock_run.assert_called_once()
        command = mock_run.call_args.args[0]
        self.assertEqual(command[1:], ["manage.py", "migrate", "--database=default"])
        value = output.getvalue()
        self.assertIn("==> migrate", value)
        self.assertIn("No migrations to apply.", value)
        self.assertIn("内部切换收尾与 migrate 已执行完成。", value)


class UploadSpecTests(TestCase):
    def test_upload_spec_builds_accept_help_widget_attrs_and_validators(self):
        spec = UploadSpec(["pdf", ".docx"], 12)

        self.assertEqual(spec.accept, ".pdf,.docx")
        self.assertEqual(spec.help_text("上传资料"), "上传资料，支持 pdf, docx，大小不超过 12MB")
        self.assertEqual(spec.widget_attrs(type="file"), {"type": "file", "accept": ".pdf,.docx"})
        self.assertEqual(len(spec.validators()), 3)

    def test_upload_size_validator_reports_chinese_error(self):
        validator = UploadSizeValidator(1)
        upload = SimpleUploadedFile("large.pdf", b"x" * (1024 * 1024 + 1))

        with self.assertRaises(ValidationError) as context:
            validator(upload)

        self.assertIn("上传文件大小不能超过 1MB。", context.exception.messages)

    def test_upload_signature_validator_accepts_matching_common_file_headers(self):
        validator = UploadSignatureValidator()

        validator(SimpleUploadedFile("sample.pdf", PDF_BYTES))
        validator(SimpleUploadedFile("sample.png", PNG_BYTES))
        validator(SimpleUploadedFile("sample.xlsx", ZIP_BYTES))
        validator(SimpleUploadedFile("sample.json", JSON_BYTES))

    def test_upload_signature_validator_rejects_mismatched_file_header(self):
        validator = UploadSignatureValidator()

        with self.assertRaises(ValidationError) as context:
            validator(SimpleUploadedFile("fake.pdf", b"not a pdf"))

        self.assertIn("文件扩展名与实际文件类型不一致", context.exception.messages[0])

    def test_upload_signature_validator_restores_file_pointer(self):
        validator = UploadSignatureValidator()
        upload = SimpleUploadedFile("sample.pdf", PDF_BYTES + b"body")
        upload.seek(5)

        validator(upload)

        self.assertEqual(upload.tell(), 5)

    def test_private_media_storage_serializes_without_absolute_path(self):
        storage = PrivateMediaStorage("assessments")

        serialized, _ = MigrationWriter.serialize(storage)

        self.assertIn("core.uploads.PrivateMediaStorage('assessments')", serialized)
        self.assertNotIn(str(Path.cwd()), serialized)
        self.assertNotIn("media-private", serialized)

    def test_private_media_storage_uses_private_media_root_setting(self):
        with TemporaryDirectory() as tmpdir, override_settings(PRIVATE_MEDIA_ROOT=tmpdir):
            storage = PrivateMediaStorage("assessments")

            self.assertEqual(
                storage.path("sample.pdf"),
                str(Path(tmpdir) / "assessments" / "sample.pdf"),
            )


class UploadUtilityTests(TestCase):
    def test_validate_upload_file_uses_upload_spec_rules(self):
        validate_upload_file(
            SimpleUploadedFile("ok.pdf", PDF_BYTES),
            allowed_extensions=["pdf"],
            max_size_mb=1,
        )

        with self.assertRaises(ValidationError):
            validate_upload_file(
                SimpleUploadedFile("bad.txt", b"bad"),
                allowed_extensions=["pdf"],
                max_size_mb=1,
            )

    def test_validate_upload_file_rejects_mismatched_signature(self):
        with self.assertRaises(ValidationError) as context:
            validate_upload_file(
                SimpleUploadedFile("fake.pdf", b"plain text"),
                allowed_extensions=["pdf"],
                max_size_mb=1,
            )

        self.assertIn("文件扩展名与实际文件类型不一致", context.exception.messages[0])

    def test_file_upload_mixin_exposes_old_validation_method_name(self):
        mixin = FileUploadMixin()
        mixin.allowed_extensions = ["pdf"]
        mixin.max_size_mb = 1

        self.assertEqual(mixin.validate_file(SimpleUploadedFile("ok.pdf", PDF_BYTES)), [])
        self.assertTrue(mixin.validate_file(SimpleUploadedFile("bad.txt", b"bad")))
        self.assertTrue(mixin.validate_file(SimpleUploadedFile("fake.pdf", b"not pdf")))

    def test_file_display_helpers_live_in_core_uploads(self):
        self.assertEqual(get_file_icon_class("report.pdf"), "icon-[tabler--file-type-pdf]")
        self.assertEqual(get_file_icon_class("archive.unknown"), "icon-[tabler--file]")
        self.assertTrue(is_image_file("photo.PNG"))
        self.assertFalse(is_image_file("report.pdf"))
        self.assertEqual(format_file_size(1024), "1.0 KB")
        self.assertEqual(format_file_size(1024 * 1024), "1.00 MB")


class MultipleFileFieldTests(TestCase):
    def test_multiple_file_field_returns_file_list(self):
        field = MultipleFileField(
            upload_spec=UploadSpec(["pdf"], 1),
            required=False,
        )
        files = [
            SimpleUploadedFile("first.pdf", PDF_BYTES),
            SimpleUploadedFile("second.pdf", PDF_BYTES),
        ]

        cleaned = field.clean(files)

        self.assertEqual([file.name for file in cleaned], ["first.pdf", "second.pdf"])

    def test_multiple_file_field_wraps_single_file_in_list(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)

        cleaned = field.clean(SimpleUploadedFile("single.pdf", PDF_BYTES))

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0].name, "single.pdf")

    def test_multiple_file_field_returns_empty_list_when_optional_and_empty(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)

        self.assertEqual(field.clean(None), [])

    def test_multiple_file_field_rejects_invalid_extension(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)

        with self.assertRaises(ValidationError):
            field.clean([SimpleUploadedFile("bad.txt", b"bad")])

    def test_multiple_file_field_rejects_oversized_file(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)
        upload = SimpleUploadedFile("large.pdf", b"x" * (1024 * 1024 + 1))

        with self.assertRaises(ValidationError):
            field.clean([upload])

    def test_multiple_file_field_rejects_mismatched_file_signature(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)

        with self.assertRaises(ValidationError):
            field.clean([SimpleUploadedFile("fake.pdf", b"not a pdf")])


class UploadSpecAdoptionTests(TestCase):
    def test_upload_forms_use_upload_spec_accept_attrs(self):
        from assessments.forms import AssessmentFileUploadForm
        from behaviors.forms import ConductRecordForm
        from meetings.forms import MeetingUploadForm
        from notices.forms import NoticeForm
        from traininglogs.forms import TrainingLogCreateForm

        self.assertEqual(
            AssessmentFileUploadForm().fields["question_file"].widget.attrs["accept"],
            ASSESSMENT_TP_UPLOAD_SPEC.accept,
        )
        self.assertEqual(
            NoticeForm().fields["attachments"].widget.attrs["accept"],
            NOTICE_ATTACHMENT_UPLOAD_SPEC.accept,
        )
        self.assertEqual(
            TrainingLogCreateForm().fields["file"].widget.attrs["accept"],
            TRAININGLOG_UPLOAD_SPEC.accept,
        )
        self.assertEqual(
            ConductRecordForm().fields["attachment"].widget.attrs["accept"],
            CONDUCT_ATTACHMENT_UPLOAD_SPEC.accept,
        )
        self.assertEqual(
            MeetingUploadForm().fields["file"].widget.attrs["accept"],
            MEETING_FILE_UPLOAD_SPEC.accept,
        )

    def test_competition_document_uses_upload_spec_help_text(self):
        from competitions.models import CompetitionProject

        field = CompetitionProject._meta.get_field("document")

        self.assertEqual(
            field.help_text,
            COMPETITION_DOCUMENT_UPLOAD_SPEC.help_text("上传与该赛项相关的归档文件"),
        )
