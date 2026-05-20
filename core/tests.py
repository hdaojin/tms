from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import django_tables2 as tables
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.writer import MigrationWriter
from django.template import Context, Template
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import resolve, reverse

from assessments.models import Assessment, AssessmentModule
from behaviors.models import ConductSummary
from competitions.models import Competition, CompetitionProject
from core.management.commands.reconcile_curriculum_training_cutovers import Command as CurriculumTrainingCutoverCommand
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
from core.utils.tables import ActionsColumn, BaseTable
from core.utils.admin_deletion import discard_registered_delete_permissions, register_delete_permission_exemptions
from curriculum.models import CompetitionType, Project, StandardModule, StandardModuleAxisMap, StandardModuleSet
from trainingcycles.models import TrainingCycle
from traininglogs.models import TrainingLog


User = get_user_model()


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
        user.user_permissions.add(Permission.objects.get(codename="add_skillposition"))

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

    def test_authenticated_page_header_includes_mobile_navigation_trigger_and_panel(self):
        user = User.objects.create_user(username="mobile-nav-header", password="testpass123")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-mobile-nav-trigger")
        self.assertContains(response, "data-mobile-nav-panel")


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


class CurriculumTrainingCutoverCommandTests(TestCase):
    def test_reconcile_curriculum_training_cutovers_is_noop_for_current_state(self):
        output = StringIO()

        call_command("reconcile_curriculum_training_cutovers", stdout=output)

        self.assertIn(
            "当前数据库已经与 curriculum/trainingcycles 的迁移状态一致，无需收尾。",
            output.getvalue(),
        )


class CursorRecorder:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql):
        self.statements.append(sql)


class QuoteOps:
    def quote_name(self, name):
        return f'"{name}"'


class FakeConnection:
    def __init__(self, vendor):
        self.vendor = vendor
        self.ops = QuoteOps()
        self.cursor_recorder = CursorRecorder()

    def cursor(self):
        return self.cursor_recorder


class CurriculumTrainingCutoverConstraintSqlTests(TestCase):
    def test_postgresql_rebuild_uses_constraint_sql(self):
        command = CurriculumTrainingCutoverCommand()
        connection = FakeConnection("postgresql")
        command._get_unique_constraints = Mock(
            return_value=[
                (
                    "traininglogs_traininglog_uploaded_by_id_training__07aa5e07_uniq",
                    {"index": False, "unique": True, "columns": ["uploaded_by_id", "training_date"]},
                )
            ]
        )
        command._has_unique_constraint = Mock(return_value=False)

        command._rebuild_traininglog_constraints(connection, {"rebuild_traininglog_unique": True})

        self.assertEqual(
            connection.cursor_recorder.statements,
            [
                'ALTER TABLE "traininglogs_traininglog" DROP CONSTRAINT "traininglogs_traininglog_uploaded_by_id_training__07aa5e07_uniq"',
                'ALTER TABLE "traininglogs_traininglog" ADD CONSTRAINT "unique_training_log_per_cycle_user_date" UNIQUE ("training_cycle_id", "uploaded_by_id", "training_date")',
            ],
        )

    def test_sqlite_rebuild_keeps_index_sql(self):
        command = CurriculumTrainingCutoverCommand()
        connection = FakeConnection("sqlite")
        command._get_unique_constraints = Mock(
            return_value=[
                (
                    "traininglogs_traininglog_uploaded_by_id_training_date_legacy_uniq",
                    {"index": True, "unique": True, "columns": ["uploaded_by_id", "training_date"]},
                )
            ]
        )
        command._has_unique_constraint = Mock(return_value=False)

        command._rebuild_traininglog_constraints(connection, {"rebuild_traininglog_unique": True})

        self.assertEqual(
            connection.cursor_recorder.statements,
            [
                'DROP INDEX "traininglogs_traininglog_uploaded_by_id_training_date_legacy_uniq"',
                'CREATE UNIQUE INDEX "unique_training_log_per_cycle_user_date" ON "traininglogs_traininglog" ("training_cycle_id", "uploaded_by_id", "training_date")',
            ],
        )


class CurriculumTrainingCutoverRecoveryTests(TransactionTestCase):
    def test_reconcile_command_recovers_legacy_curriculum_and_training_state(self):
        with TemporaryDirectory() as temp_dir, override_settings(MEDIA_ROOT=temp_dir):
            competition_type = CompetitionType.objects.create(
                code="WSC-LEGACY",
                name="历史迁移赛事",
            )
            project = Project.objects.create(
                competition_type=competition_type,
                code="LEGACY",
                name="历史迁移项目",
            )
            module_set = project.get_or_create_default_standard_module_set()
            module = StandardModule.objects.create(
                project=project,
                module_set=module_set,
                code="A",
                name="历史模块",
            )
            competition = Competition.objects.create(
                competition_type=competition_type,
                name="第 47 届世界技能大赛",
                code="WSC47",
            )
            CompetitionProject.objects.create(
                competition=competition,
                project=project,
            )
            user = User.objects.create_user(username="legacy-user", password="testpass123")
            training_cycle = TrainingCycle.objects.create(
                code="TC-LEGACY",
                name="旧训练周期",
                project=project,
                module_set=module_set,
                start_date=date(2026, 4, 17),
                end_date=date(2026, 5, 16),
                status=TrainingCycle.Status.COMPLETED,
            )
            training_log = TrainingLog.objects.create(
                training_cycle=training_cycle,
                module=module,
                task="历史日志",
                training_date=date(2026, 4, 17),
                file=SimpleUploadedFile("legacy.pdf", b"%PDF-1.4 legacy", content_type="application/pdf"),
                uploaded_by=user,
            )
            assessment = Assessment.objects.create(
                name="历史考核",
                training_cycle=training_cycle,
                start_date=date(2026, 5, 1),
                end_date=date(2026, 5, 2),
            )
            AssessmentModule.objects.create(
                assessment=assessment,
                module=module,
            )

            old_content_type = ContentType.objects.create(app_label="competitions", model="project")
            Permission.objects.create(
                name="旧项目查看权限",
                codename="view_project_legacy",
                content_type=old_content_type,
            )
            ContentType.objects.filter(app_label="trainingcycles", model="trainingcycle").delete()
            MigrationRecorder.Migration.objects.filter(app="curriculum", name="0001_initial").delete()
            MigrationRecorder.Migration.objects.filter(app="trainingcycles", name="0001_initial").delete()
            MigrationRecorder.Migration.objects.filter(app="assessments", name="0002_initial").delete()

            self._convert_database_to_legacy_shape()

            output = StringIO()
            call_command("reconcile_curriculum_training_cutovers", "--execute", stdout=output)

        self.assertIn("curriculum/trainingcycles 收尾已完成", output.getvalue())
        self.assertTrue(self._table_exists("curriculum_project"))
        self.assertFalse(self._table_exists("competitions_project"))
        self.assertTrue(self._table_exists("trainingcycles_trainingcycle"))
        self.assertTrue(
            MigrationRecorder.Migration.objects.filter(app="curriculum", name="0001_initial").exists()
        )
        self.assertTrue(
            MigrationRecorder.Migration.objects.filter(app="trainingcycles", name="0001_initial").exists()
        )
        self.assertTrue(
            MigrationRecorder.Migration.objects.filter(app="assessments", name="0002_initial").exists()
        )
        self.assertFalse(ContentType.objects.filter(app_label="competitions", model="project").exists())
        self.assertTrue(ContentType.objects.filter(app_label="trainingcycles", model="trainingcycle").exists())
        self.assertTrue(
            Permission.objects.filter(
                codename="view_project_legacy",
                content_type__app_label="curriculum",
            ).exists()
        )

        project.refresh_from_db()
        training_log.refresh_from_db()
        assessment.refresh_from_db()
        generated_cycle = TrainingCycle.objects.get()

        self.assertEqual(project.competition_type_id, competition_type.pk)
        self.assertEqual(training_log.training_cycle_id, generated_cycle.pk)
        self.assertEqual(assessment.training_cycle_id, generated_cycle.pk)
        self.assertEqual(generated_cycle.project_id, project.pk)
        self.assertEqual(generated_cycle.module_set_id, module_set.pk)
        self.assertEqual(generated_cycle.start_date, date(2026, 4, 17))
        self.assertEqual(generated_cycle.end_date, date(2026, 5, 2))

    def _convert_database_to_legacy_shape(self):
        with connection.constraint_checks_disabled():
            with connection.schema_editor(atomic=False) as schema_editor:
                schema_editor.alter_db_table(
                    CompetitionType,
                    CompetitionType._meta.db_table,
                    "competitions_competitiontype",
                )
                schema_editor.alter_db_table(
                    Project,
                    Project._meta.db_table,
                    "competitions_project",
                )
                schema_editor.alter_db_table(
                    StandardModuleSet,
                    StandardModuleSet._meta.db_table,
                    "competitions_standardmoduleset",
                )
                schema_editor.alter_db_table(
                    StandardModule,
                    StandardModule._meta.db_table,
                    "competitions_standardmodule",
                )
                schema_editor.alter_db_table(
                    StandardModuleAxisMap,
                    StandardModuleAxisMap._meta.db_table,
                    "competitions_standardmoduleaxismap",
                )

            with connection.cursor() as cursor:
                cursor.execute("PRAGMA foreign_keys = OFF")
                cursor.execute(
                    """
                    CREATE TABLE traininglogs_traininglog_legacy (
                        id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                        task varchar(100) NOT NULL,
                        training_date date NOT NULL,
                        file varchar(100) NOT NULL,
                        uploaded_at datetime NOT NULL,
                        module_id bigint NULL,
                        uploaded_by_id integer NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO traininglogs_traininglog_legacy (id, task, training_date, file, uploaded_at, module_id, uploaded_by_id)
                    SELECT id, task, training_date, file, uploaded_at, module_id, uploaded_by_id
                    FROM traininglogs_traininglog
                    """
                )
                cursor.execute("DROP TABLE traininglogs_traininglog")
                cursor.execute("ALTER TABLE traininglogs_traininglog_legacy RENAME TO traininglogs_traininglog")
                cursor.execute(
                    "CREATE UNIQUE INDEX traininglogs_traininglog_uploaded_by_id_training_date_legacy_uniq "
                    "ON traininglogs_traininglog (uploaded_by_id, training_date)"
                )

                cursor.execute(
                    """
                    CREATE TABLE assessments_assessment_legacy (
                        id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                        name varchar(100) NOT NULL,
                        description text NOT NULL,
                        created_at datetime NOT NULL,
                        updated_at datetime NOT NULL,
                        end_date date NOT NULL,
                        start_date date NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO assessments_assessment_legacy (id, name, description, created_at, updated_at, end_date, start_date)
                    SELECT id, name, description, created_at, updated_at, end_date, start_date
                    FROM assessments_assessment
                    """
                )
                cursor.execute("DROP TABLE assessments_assessment")
                cursor.execute("ALTER TABLE assessments_assessment_legacy RENAME TO assessments_assessment")

                cursor.execute("DROP TABLE trainingcycles_trainingcycle")
                cursor.execute(
                    """
                    CREATE TABLE competitions_project_legacy (
                        id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                        code varchar(50) NOT NULL,
                        name varchar(100) NOT NULL,
                        description text NOT NULL,
                        created_at datetime NOT NULL,
                        updated_at datetime NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO competitions_project_legacy (id, code, name, description, created_at, updated_at)
                    SELECT id, code, name, description, created_at, updated_at
                    FROM competitions_project
                    """
                )
                cursor.execute("DROP TABLE competitions_project")
                cursor.execute("ALTER TABLE competitions_project_legacy RENAME TO competitions_project")
                cursor.execute("PRAGMA foreign_keys = ON")

    def _table_exists(self, table_name):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = %s",
                [table_name],
            )
            return cursor.fetchone() is not None


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
