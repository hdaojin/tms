from datetime import date, datetime, timedelta, timezone as datetime_timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import TrainingLogForm
from .log_files import DUPLICATE_LOG_MESSAGE
from .models import TrainingCycle, TrainingCycleMember, TrainingLog
from .services import save_training_log
from .tables import TrainingLogTable
from .tests import TrainingFixtureMixin, User


class TrainingLogWorkflowTests(TrainingFixtureMixin, TestCase):
    def test_record_times_survive_edits_and_refresh_on_unchanged_save(self):
        created = datetime(2026, 10, 20, 1, 2, 3, tzinfo=datetime_timezone.utc)
        with patch("django.utils.timezone.now", return_value=created):
            log = self.create_log()
        self.assertEqual(log.created_at, created)
        self.assertEqual(log.updated_at, created)
        for index, summary in enumerate(["更新摘要", "更新摘要"], start=1):
            saved = created + timedelta(hours=index)
            form = TrainingLogForm(self.data(summary=summary), instance=log, author=self.user)
            self.assertTrue(form.is_valid(), form.errors)
            with patch("django.utils.timezone.now", return_value=saved):
                form.save()
            log.refresh_from_db()
            self.assertEqual(log.created_at, created)
            self.assertEqual(log.updated_at, saved)

    def test_list_and_detail_show_record_times_and_author_name(self):
        created = datetime(2026, 10, 20, 1, 2, 3, tzinfo=datetime_timezone.utc)
        changed = created + timedelta(hours=1)
        with patch("django.utils.timezone.now", return_value=created):
            log = self.create_log()
        with patch("django.utils.timezone.now", return_value=changed):
            save_training_log(log, [])
        table = TrainingLogTable([log])
        self.assertEqual(table.rows[0].get_cell("author"), "夏国金")
        response = self.client.get(reverse("training:log_list"))
        self.assertContains(response, "夏国金")
        self.assertNotContains(response, "创建时间")
        self.assertNotContains(response, "修改时间")
        response = self.client.get(reverse("training:log_detail", args=[log.pk]))
        for text in ["创建时间", "修改时间", "2026-10-20 09:02:03", "2026-10-20 10:02:03", "夏国金"]:
            self.assertContains(response, text)
        self.assertNotContains(response, "上传时间")
        self.user.first_name = self.user.last_name = ""
        self.assertEqual(TrainingLogTable([log]).rows[0].get_cell("author"), self.user.username)

    def test_list_shows_content_and_attachment_without_summary_links_or_task_count(self):
        log = self.create_log(summary="<script>不执行</script>训练摘要")
        TrainingLog.objects.create(
            training_cycle=self.period, author=self.user, training_date=date(2026, 3, 3), topic="文字日志"
        )
        with patch.object(log.document.storage, "open", side_effect=AssertionError("列表不应读取文件")):
            response = self.client.get(reverse("training:log_list"))
        for text in ["训练内容", "日志附件", "未附文件", log.canonical_filename]:
            self.assertContains(response, text)
        for text in ["关联任务数", "暂无摘要", "训练摘要"]:
            self.assertNotContains(response, text)
        records = list(response.context["table"].data)
        self.assertEqual([record.execution_count for record in records], [0, 0])
        with self.assertNumQueries(0):
            table = TrainingLogTable(records)
            for row in table.rows:
                row.get_cell("author")
                row.get_cell("training_cycle")
                row.get_cell("document")
                content = row.get_cell("topic")
                self.assertIn(row.record.topic, content)
                self.assertNotIn("<a", content)
            self.assertNotIn("execution_count", table.columns.names())

    def test_admin_displays_readonly_record_times_and_name(self):
        log = self.create_log()
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        response = self.client.get(reverse("admin:training_traininglog_changelist"))
        self.assertEqual(response.status_code, 200)
        for text in ["创建时间", "更新时间", "夏国金", "有附件"]:
            self.assertContains(response, text)
        response = self.client.get(reverse("admin:training_traininglog_change", args=[log.pk]))
        self.assertEqual(response.status_code, 200)
        form = response.context["adminform"]
        self.assertIn("created_at", form.readonly_fields)
        self.assertIn("updated_at", form.readonly_fields)
        self.assertNotIn("created_at", form.form.fields)
        self.assertNotIn("updated_at", form.form.fields)
        self.assertContains(response, "创建时间")
        self.assertContains(response, "更新时间")

    def setUp(self):
        super().setUp()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(PRIVATE_MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.project.name = "网络系统管理项目"
        self.project.save()
        self.user = User.objects.create_user("competitor", last_name="夏", first_name="国金")
        self.coach = User.objects.create_user("coach", last_name="肖", first_name="威")
        self.period = self.active_cycle(end_date=None)
        for user, role in [(self.user, "competitor"), (self.coach, "coach")]:
            TrainingCycleMember.objects.create(training_cycle=self.period, user=user, role=role, is_current=True)
        self.grant(self.user, "view_traininglog", "add_traininglog", "change_traininglog")
        self.client.force_login(self.user)

    def grant(self, user, *codenames):
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="training", codename__in=codenames))
        for name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            user.__dict__.pop(name, None)

    def active_cycle(self, code="C1", **kwargs):
        cycle = self.cycle(code, **kwargs)
        self.bind(cycle)
        cycle.status = TrainingCycle.Status.ACTIVE
        cycle.save()
        return cycle

    def data(self, **kwargs):
        return {"training_cycle": self.period.pk, "training_date": "2026-03-02", "topic": "训练日志", **kwargs}

    def upload(self, filename="original.pdf"):
        return SimpleUploadedFile(filename, b"%PDF-1.4\n%%EOF", content_type="application/pdf")

    def create_log(self, user=None, **kwargs):
        backfill = kwargs.pop("backfill", False)
        form = TrainingLogForm(self.data(**kwargs), {"document": self.upload()}, author=user or self.user,
                               backfill=backfill)
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def test_defaults_use_explicit_current_membership_and_iso_today(self):
        today = timezone.localdate()
        recent = self.active_cycle("RECENT", start_date=today - timedelta(days=1), end_date=None)
        TrainingCycleMember.objects.create(training_cycle=recent, user=self.user, role="competitor")
        self.active_cycle("UNJOINED", start_date=today, end_date=None)
        response = self.client.get(reverse("training:log_create"))
        form = response.context["form"]
        self.assertEqual(form["training_cycle"].value(), self.period.pk)
        self.assertNotContains(response, '<select name="training_cycle"')
        self.assertContains(response, f'value="{today:%Y-%m-%d}"')
        recent.status = "completed"
        recent.save()
        self.period.status = "completed"
        self.period.save()
        self.assertIsNone(TrainingLogForm(author=self.user)["training_cycle"].value())

    def test_names_roles_original_extension_and_training_month(self):
        for user, label in [(self.user, "选手日志-夏国金"), (self.coach, "教练日志-肖威")]:
            form = TrainingLogForm(self.data(), {"document": self.upload("original.PDF")}, author=user)
            self.assertTrue(form.is_valid(), form.errors)
            log = form.save()
            expected = f"网络系统管理项目2026年03月02日{label}.PDF"
            self.assertEqual(log.canonical_filename, expected)
            self.assertEqual(log.document.name, f"logs/C1/2026/03/{expected}")
            self.assertTrue(log.document.storage.exists(log.document.name))

    def test_duplicate_author_day_and_same_name_different_author(self):
        self.create_log()
        form = TrainingLogForm(self.data(), {"document": SimpleUploadedFile("different.txt", b"text")}, author=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn(DUPLICATE_LOG_MESSAGE, str(form.errors))
        other = User.objects.create_user("same_name", last_name="夏", first_name="国金")
        TrainingCycleMember.objects.create(training_cycle=self.period, user=other, role="competitor", is_current=True)
        form = TrainingLogForm(self.data(), {"document": self.upload()}, author=other)
        self.assertFalse(form.is_valid())
        self.assertIn(DUPLICATE_LOG_MESSAGE, str(form.errors))

    def test_same_name_allowed_in_different_cycle(self):
        self.create_log()
        other = self.active_cycle("OTHER", end_date=None)
        TrainingCycleMember.objects.create(training_cycle=other, user=self.user, role="competitor")
        log = self.create_log(training_cycle=other.pk, backfill=True)
        self.assertIn("logs/OTHER/2026/03/", log.document.name)

    def test_membership_always_required_and_real_name_required_only_for_file(self):
        outsider = User.objects.create_user("outsider", last_name="张", first_name="三")
        form = TrainingLogForm(self.data(), {"document": self.upload()}, author=outsider)
        self.assertFalse(form.is_valid())
        self.assertIn("当前周期", str(form.errors))
        self.assertFalse(TrainingLogForm(self.data(), author=outsider).is_valid())
        self.user.first_name = self.user.last_name = ""
        self.user.save()
        form = TrainingLogForm(self.data(), {"document": self.upload()}, author=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("真实姓名", str(form.errors))
        form = TrainingLogForm(self.data(), author=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        log = form.save()
        response = self.client.get(reverse("training:log_detail", args=[log.pk]))
        self.assertContains(response, "这是一条文字日志")
        self.assertNotContains(response, "下载文件")

    def test_locked_fields_ignore_tampered_post_and_replacement(self):
        log = self.create_log()
        original = log.document.name
        other = self.cycle("OTHER")
        form = TrainingLogForm(
            self.data(training_cycle=other.pk, training_date="2026-04-01", summary="更新摘要"),
            {"document": self.upload("replacement.pdf")}, instance=log, author=self.coach,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        log.refresh_from_db()
        self.assertEqual(log.document.name, original)
        self.assertEqual(log.training_cycle, self.period)
        self.assertEqual(log.training_date, date(2026, 3, 2))
        self.assertEqual(log.author, self.user)
        self.assertEqual(log.summary, "更新摘要")

    def test_preview_download_detail_and_object_scope(self):
        log = self.create_log()
        response = self.client.get(reverse("training:log_detail", args=[log.pk]))
        self.assertTemplateUsed(response, "common/file_preview_detail.html")
        self.assertContains(response, "PDF 预览")
        for route in ("log_preview", "log_download"):
            response = self.client.get(reverse(f"training:{route}", args=[log.pk]))
            self.assertEqual(response.status_code, 200)
            response.close()
        self.grant(self.coach, "view_traininglog")
        self.client.force_login(self.coach)
        for route in ("log_detail", "log_preview", "log_download"):
            self.assertEqual(self.client.get(reverse(f"training:{route}", args=[log.pk])).status_code, 404)

    def test_delete_requires_permission_and_confirmation_and_cleans_file(self):
        log = self.create_log()
        url = reverse("training:log_delete", args=[log.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.grant(self.user, "delete_traininglog")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(TrainingLog.objects.filter(pk=log.pk).exists())
        name, storage = log.document.name, log.document.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(TrainingLog.objects.filter(pk=log.pk).exists())
        self.assertFalse(storage.exists(name))
        self.create_log()

    def test_edit_all_does_not_grant_delete_all(self):
        log = self.create_log()
        self.grant(self.coach, "view_traininglog", "delete_traininglog", "change_all_traininglog", "view_all_traininglog")
        self.client.force_login(self.coach)
        url = reverse("training:log_delete", args=[log.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.grant(self.coach, "delete_all_traininglog")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(url).status_code, 302)

    def test_delete_rollback_preserves_file(self):
        log = self.create_log()
        pk, name, storage = log.pk, log.document.name, log.document.storage
        with self.assertRaises(RuntimeError), transaction.atomic():
            log.delete()
            raise RuntimeError("rollback")
        self.assertTrue(TrainingLog.objects.filter(pk=pk).exists())
        self.assertTrue(storage.exists(name))

    def test_database_unique_filename_and_storage_no_random_suffix(self):
        log = self.create_log()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrainingLog.objects.create(training_cycle=self.period, author=self.coach, training_date=date(2026, 3, 2),
                                       topic="重复", canonical_filename=log.canonical_filename)
        with self.assertRaises(ValidationError):
            log.document.storage.save(log.document.name, self.upload())
        self.assertEqual(len(list(Path(self.media.name).rglob("*.pdf"))), 1)

    def test_failed_save_cleans_new_file_and_record(self):
        form = TrainingLogForm(self.data(), {"document": self.upload()}, author=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        original_save = TrainingLog.save

        def fail_file_update(instance, *args, **kwargs):
            if "document" in (kwargs.get("update_fields") or []):
                raise RuntimeError("database failure")
            return original_save(instance, *args, **kwargs)

        with patch.object(TrainingLog, "save", fail_file_update), self.assertRaises(RuntimeError):
            form.save()
        self.assertFalse(TrainingLog.objects.exists())
        self.assertEqual(list(Path(self.media.name).rglob("*.pdf")), [])

    def test_text_log_can_add_file_and_historical_file_stays_untouched(self):
        log = TrainingLog.objects.create(training_cycle=self.period, author=self.user, training_date=date(2026, 3, 2),
                                         topic="文字日志")
        form = TrainingLogForm(self.data(), {"document": self.upload()}, instance=log, author=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        legacy = TrainingLog.objects.create(training_cycle=self.period, author=self.coach, training_date=date(2026, 3, 2),
                                            topic="历史", document="logs/C1/2/old.pdf")
        form = TrainingLogForm(self.data(summary="说明"), instance=legacy, author=self.coach)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        legacy.refresh_from_db()
        self.assertEqual(legacy.document.name, "logs/C1/2/old.pdf")
        self.assertIsNone(legacy.canonical_filename)

    def test_service_rejects_duplicate_day_before_writing_file(self):
        self.create_log()
        log = TrainingLog(training_cycle=self.period, author=self.user, training_date=date(2026, 3, 2),
                          topic="并发重复", document=self.upload())
        with self.assertRaisesMessage(ValidationError, DUPLICATE_LOG_MESSAGE):
            save_training_log(log, [])
        self.assertEqual(len(list(Path(self.media.name).rglob("*.pdf"))), 1)

    def test_http_upload_duplicate_and_delete_return_to_list(self):
        url = reverse("training:log_create")
        response = self.client.post(url, self.data(document=self.upload()))
        log = TrainingLog.objects.get(author=self.user)
        self.assertRedirects(response, reverse("training:log_detail", args=[log.pk]))
        response = self.client.post(url, self.data(document=self.upload()))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, DUPLICATE_LOG_MESSAGE)
        self.assertEqual(TrainingLog.objects.count(), 1)
        self.grant(self.user, "delete_traininglog")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("training:log_delete", args=[log.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "新增训练日志")

    def test_orphaned_storage_collision_returns_form_error_without_new_record(self):
        filename = "logs/C1/2026/03/网络系统管理项目2026年03月02日选手日志-夏国金.pdf"
        storage = TrainingLog._meta.get_field("document").storage
        storage.save(filename, self.upload())
        response = self.client.post(reverse("training:log_create"), self.data(document=self.upload()))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, DUPLICATE_LOG_MESSAGE)
        self.assertFalse(TrainingLog.objects.exists())
        self.assertTrue(storage.exists(filename))
