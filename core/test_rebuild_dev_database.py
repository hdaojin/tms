from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.sites.models import Site
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, override_settings

from accounts.bootstrap import DEFAULT_ROLES
from assessments.bootstrap import COMPETITION_ROLES
from assessments.models import CompetitionRole
from feedback.models import Feedback, FeedbackAttachment, FeedbackCategory

COMMAND_MODULE = "core.management.commands.rebuild_dev_database"


@override_settings(DEBUG=True)
class RebuildDevDatabaseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("reset-admin", password="test-password")
        self.old_role = CompetitionRole.objects.create(code="obsolete", name="旧角色", category="other")
        self.feedback = Feedback.objects.create(
            category=FeedbackCategory.objects.create(code="reset-test", name="测试分类"),
            author=self.user, title="测试反馈", content="待清空",
        )

    def run_command(self, **options):
        output = StringIO()
        call_command("rebuild_dev_database", stdout=output, **options)
        return output.getvalue()

    def assert_original_data_exists(self):
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk, username="reset-admin").exists())
        self.assertTrue(CompetitionRole.objects.filter(code="obsolete").exists())
        self.assertTrue(Feedback.objects.filter(pk=self.feedback.pk).exists())

    def test_dry_run_is_read_only_even_with_yes(self):
        with patch(f"{COMMAND_MODULE}.call_command") as flush, patch("builtins.input") as prompt:
            output = self.run_command(dry_run=True, yes=True)
        flush.assert_not_called()
        prompt.assert_not_called()
        self.assert_original_data_exists()
        self.assertIn(str(connection.settings_dict["NAME"]), output)
        self.assertIn("赛项经理", output)
        self.assertIn("备选选手", output)
        self.assertIn("数据库未写入", output)

    def test_cancel_and_eof_do_not_clear_data(self):
        with patch("builtins.input", return_value="y"):
            self.assertIn("已取消", self.run_command())
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaisesMessage(CommandError, "无法读取确认"):
                self.run_command()
        self.assert_original_data_exists()

    @override_settings(DEBUG=False)
    def test_non_debug_rejected_including_dry_run_and_yes(self):
        with self.assertRaisesMessage(CommandError, "DEBUG=True"):
            self.run_command(yes=True, dry_run=True)
        self.assert_original_data_exists()

    def test_unsupported_backend_rejected(self):
        with patch.object(connection, "vendor", "mysql"):
            with self.assertRaisesMessage(CommandError, "仅支持 SQLite 和 PostgreSQL"):
                self.run_command(yes=True)
        self.assert_original_data_exists()

    def test_database_router_rejected(self):
        with override_settings(DATABASE_ROUTERS=[object()]):
            with self.assertRaisesMessage(CommandError, "无数据库路由"):
                self.run_command(yes=True)
        self.assert_original_data_exists()

    def test_unmanaged_tables_rejected_without_writing(self):
        original = connection.introspection.table_names
        with patch.object(connection.introspection, "table_names", side_effect=lambda *args, **kwargs: [*original(*args, **kwargs), "legacy_table"]):
            with self.assertRaisesMessage(CommandError, "legacy_table"):
                self.run_command(yes=True)
        self.assert_original_data_exists()

    def test_pending_migrations_rejected(self):
        with patch(f"{COMMAND_MODULE}.MigrationExecutor") as executor:
            executor.return_value.migration_plan.return_value = [object()]
            with self.assertRaisesMessage(CommandError, "未应用的迁移"):
                self.run_command(yes=True)
        self.assert_original_data_exists()

    def test_rebuild_restores_only_current_defaults_and_preserves_file_and_migrations(self):
        migrations = set(MigrationRecorder.Migration.objects.values_list("app", "name"))
        with TemporaryDirectory() as directory:
            storage = FileSystemStorage(location=directory)
            field = FeedbackAttachment._meta.get_field("file")
            with patch.object(field, "storage", storage):
                attachment = FeedbackAttachment.objects.create(
                    feedback=self.feedback, file=ContentFile(b"keep upload", name="keep.txt"),
                    original_filename="keep.txt", file_size=11, uploaded_by=self.user,
                )
                path = Path(attachment.file.path)
                with patch("builtins.input", return_value="yes"):
                    output = self.run_command()
                self.assertEqual(path.read_bytes(), b"keep upload")
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Feedback.objects.exists())
        self.assertFalse(FeedbackAttachment.objects.exists())
        self.assertEqual(set(CompetitionRole.objects.values_list("code", flat=True)), {r["code"] for r in COMPETITION_ROLES})
        self.assertEqual(CompetitionRole.objects.get(code="coach").category, "expert")
        self.assertEqual(set(Group.objects.values_list("name", flat=True)), {r["name"] for r in DEFAULT_ROLES})
        self.assertTrue(Permission.objects.filter(codename="view_competitionrole").exists())
        self.assertTrue(Site.objects.filter(pk=1).exists())
        self.assertEqual(set(MigrationRecorder.Migration.objects.values_list("app", "name")), migrations)
        self.assertIn("createsuperuser", output)
        # 重复重建也不会混入历史迁移中的角色。
        self.run_command(yes=True)
        self.assertEqual(CompetitionRole.objects.count(), len(COMPETITION_ROLES))

    def test_bootstrap_failure_rolls_back_flush_and_partial_writes(self):
        def fail_after_write():
            CompetitionRole.objects.create(code="partial", name="不应保留", category="other")
            raise ValueError("invalid declaration")

        with patch(f"{COMMAND_MODULE}.bootstrap_defaults", side_effect=fail_after_write):
            with self.assertRaisesMessage(CommandError, "已回滚"):
                self.run_command(yes=True)
        self.assert_original_data_exists()
        self.assertFalse(CompetitionRole.objects.filter(code="partial").exists())
