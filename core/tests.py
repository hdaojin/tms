from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db.migrations.writer import MigrationWriter
from django.test import TestCase, override_settings
from django.urls import reverse

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
    UploadSizeValidator,
    UploadSpec,
    format_file_size,
    get_file_icon_class,
    is_image_file,
    validate_upload_file,
)


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
        self.assertEqual(len(spec.validators()), 2)

    def test_upload_size_validator_reports_chinese_error(self):
        validator = UploadSizeValidator(1)
        upload = SimpleUploadedFile("large.pdf", b"x" * (1024 * 1024 + 1))

        with self.assertRaises(ValidationError) as context:
            validator(upload)

        self.assertIn("上传文件大小不能超过 1MB。", context.exception.messages)

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
            SimpleUploadedFile("ok.pdf", b"ok"),
            allowed_extensions=["pdf"],
            max_size_mb=1,
        )

        with self.assertRaises(ValidationError):
            validate_upload_file(
                SimpleUploadedFile("bad.txt", b"bad"),
                allowed_extensions=["pdf"],
                max_size_mb=1,
            )

    def test_file_upload_mixin_exposes_old_validation_method_name(self):
        mixin = FileUploadMixin()
        mixin.allowed_extensions = ["pdf"]
        mixin.max_size_mb = 1

        self.assertEqual(mixin.validate_file(SimpleUploadedFile("ok.pdf", b"ok")), [])
        self.assertTrue(mixin.validate_file(SimpleUploadedFile("bad.txt", b"bad")))

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
            SimpleUploadedFile("first.pdf", b"first"),
            SimpleUploadedFile("second.pdf", b"second"),
        ]

        cleaned = field.clean(files)

        self.assertEqual([file.name for file in cleaned], ["first.pdf", "second.pdf"])

    def test_multiple_file_field_wraps_single_file_in_list(self):
        field = MultipleFileField(upload_spec=UploadSpec(["pdf"], 1), required=False)

        cleaned = field.clean(SimpleUploadedFile("single.pdf", b"single"))

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
