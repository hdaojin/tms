from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import TrainingLogForm, TrainingLogTemplateForm
from .log_templates import save_log_template, delete_log_template
from .models import TrainingCycle, TrainingCycleMember, TrainingLog, TrainingLogTemplate
from .services import save_training_log
from .tests import TrainingFixtureMixin, User


class LogTemplateTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.enterContext(override_settings(PRIVATE_MEDIA_ROOT=self.media.name))
        self.manager = User.objects.create_user("manager")
        self.student = User.objects.create_user("student", last_name="测", first_name="试")
        self.outsider = User.objects.create_user("outsider")
        self.grant(self.manager, *(f"{action}_traininglogtemplate" for action in ("view", "add", "change", "delete")))
        self.grant(self.student, "add_traininglog")
        self.grant(self.outsider, "add_traininglog")
        self.cycle1 = self.active_cycle("C1")
        self.cycle2 = self.active_cycle("C2")
        TrainingCycleMember.objects.create(training_cycle=self.cycle1, user=self.student,
                                           role="competitor", is_current=True)
        TrainingCycleMember.objects.create(training_cycle=self.cycle2, user=self.student, role="competitor")
        self.template1 = self.template(self.cycle1, "周期一模板")
        self.template2 = self.template(self.cycle2, "周期二模板")
        self.client.force_login(self.student)

    def grant(self, user, *codes):
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label="training", codename__in=codes))
        for key in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            user.__dict__.pop(key, None)

    def active_cycle(self, code):
        cycle = self.cycle(code, end_date=None)
        self.bind(cycle)
        cycle.status = TrainingCycle.Status.ACTIVE
        cycle.save()
        return cycle

    def upload(self, name="template.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4\ntraining")

    def template(self, cycle, name):
        return save_log_template(TrainingLogTemplate(name=name, training_cycle=cycle, file=self.upload()),
                                 actor=self.manager)

    def url(self, template, *, backfill=False):
        return reverse("training:log_template_download", args=[template.pk]) + ("?backfill=1" if backfill else "")

    def test_daily_and_backfill_sections_follow_authorized_cycle(self):
        daily = self.client.get(reverse("training:log_create"))
        self.assertContains(daily, self.template1.name)
        self.assertNotContains(daily, self.template2.name)
        self.assertContains(daily, self.url(self.template1))
        self.assertNotContains(daily, f'href="{reverse("training:log_template_list")}"')
        backfill = self.client.get(reverse("training:log_backfill"))
        self.assertContains(backfill, 'hx-target="#log-template-downloads"')
        fragment = self.client.get(reverse("training:log_template_links"), {"training_cycle": self.cycle2.pk})
        self.assertContains(fragment, self.template2.name)
        self.assertNotContains(fragment, self.template1.name)
        for value in ("bad", "9" * 100, "", "-1"):
            response = self.client.get(reverse("training:log_template_links"), {"training_cycle": value})
            self.assertNotContains(response, self.template1.name)
            self.assertNotContains(response, self.template2.name)
        # 表单校验失败后仍按提交的周期展示模板。
        response = self.client.post(reverse("training:log_backfill"), {"training_cycle": self.cycle2.pk})
        self.assertContains(response, self.template2.name)

    def test_download_rechecks_membership_state_permission_and_active_flag(self):
        response = self.client.get(self.url(self.template1))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        response.close()
        self.assertEqual(self.client.get(self.url(self.template2)).status_code, 404)
        response = self.client.get(self.url(self.template2, backfill=True))
        self.assertEqual(response.status_code, 200)
        response.close()
        for status in ("preparing", "archived"):
            TrainingCycle.objects.filter(pk=self.cycle2.pk).update(status=status)
            self.assertEqual(self.client.get(self.url(self.template2, backfill=True)).status_code, 404)
        TrainingCycle.objects.filter(pk=self.cycle2.pk).update(status="completed")
        response = self.client.get(self.url(self.template2, backfill=True))
        self.assertEqual(response.status_code, 200)
        response.close()
        self.template1.is_active = False
        save_log_template(self.template1, actor=self.manager)
        self.assertEqual(self.client.get(self.url(self.template1)).status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url(self.template2, backfill=True)).status_code, 404)
        self.student.user_permissions.clear()
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url(self.template2, backfill=True)).status_code, 404)
        self.assertEqual(self.client.get(reverse("training:log_template_links")).status_code, 403)
        self.client.force_login(self.manager)
        response = self.client.get(self.url(self.template1))
        self.assertEqual(response.status_code, 200)
        response.close()
        self.template1.file.storage.delete(self.template1.file.name)
        self.assertEqual(self.client.get(self.url(self.template1)).status_code, 404)
        self.assertTrue(TrainingLogTemplate.objects.filter(pk=self.template1.pk).exists())
        self.client.logout()
        self.assertEqual(self.client.get(self.url(self.template1)).status_code, 302)

    def test_management_permissions_menu_and_crud(self):
        listing = reverse("training:log_template_list")
        create = reverse("training:log_template_create")
        edit = reverse("training:log_template_edit", args=[self.template1.pk])
        delete = reverse("training:log_template_delete", args=[self.template1.pk])
        for url in (listing, create, edit, delete):
            self.assertEqual(self.client.get(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            save_log_template(self.template1, actor=self.student)
        self.grant(self.student, "view_traininglogtemplate")
        self.assertContains(self.client.get(listing), listing)
        self.assertNotContains(self.client.get(listing), create)
        for url in (create, edit, delete):
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.force_login(self.manager)
        response = self.client.post(create, {"name": "新模板", "training_cycle": self.cycle1.pk,
                                            "file": self.upload(), "order": 2, "is_active": "on"})
        self.assertRedirects(response, listing)
        response = self.client.post(edit, {"name": "已修改", "training_cycle": self.cycle1.pk,
                                          "order": 0, "description": "使用说明"})
        self.assertRedirects(response, listing)
        self.template1.refresh_from_db()
        self.assertFalse(self.template1.is_active)
        self.assertEqual(self.template1.name, "已修改")
        self.assertContains(self.client.get(delete), "确认删除")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertRedirects(self.client.post(delete), listing)
        self.assertFalse(TrainingLogTemplate.objects.filter(pk=self.template1.pk).exists())

    def test_replacement_deletion_and_failed_save_cleanup(self):
        storage = self.template1.file.storage
        old_name = self.template1.file.name
        self.template1.file = self.upload("new.pdf")
        with self.captureOnCommitCallbacks(execute=True):
            save_log_template(self.template1, actor=self.manager)
        self.assertFalse(storage.exists(old_name))
        new_name = self.template1.file.name
        self.template1.file = self.upload("failed.pdf")
        original_save = TrainingLogTemplate.save

        def fail_after_file_save(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)
            raise RuntimeError("写入失败")

        with patch.object(TrainingLogTemplate, "save", fail_after_file_save):
            with self.assertRaises(RuntimeError):
                save_log_template(self.template1, actor=self.manager)
        self.assertTrue(storage.exists(new_name))
        self.assertFalse(list(Path(self.media.name).rglob("failed.pdf")))
        self.template1.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            delete_log_template(self.template1, actor=self.manager)
        self.assertFalse(storage.exists(new_name))

    def test_only_doc_docx_pdf_accepted_and_legacy_text_is_preserved(self):
        today = timezone.localdate()
        for extension in ("txt", "md", "xlsx", "exe"):
            upload = SimpleUploadedFile(f"template.{extension}", b"text")
            form = TrainingLogTemplateForm({"name": "不允许", "training_cycle": self.cycle1.pk, "order": 0},
                                           {"file": upload})
            self.assertFalse(form.is_valid())
            self.assertIn("file", form.errors)
            log = TrainingLog(training_cycle=self.cycle1, author=self.student,
                              training_date=today, document=upload)
            with self.assertRaises(ValidationError):
                save_training_log(log, [])
            form = TrainingLogForm({"training_date": (today - timedelta(days=1)).isoformat(),
                                    "training_cycle": self.cycle1.pk}, {"document": upload},
                                   author=self.student, backfill=True)
            self.assertFalse(form.is_valid())
            self.assertIn("document", form.errors)
        legacy = TrainingLog.objects.create(training_cycle=self.cycle1, author=self.student,
                                             training_date=today - timedelta(days=1), document="old.txt")
        form = TrainingLogForm({"summary": "保留", "training_date": legacy.training_date.isoformat()},
                               instance=legacy, author=self.student)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        legacy.refresh_from_db()
        self.assertEqual(legacy.document.name, "old.txt")

    def test_supported_documents_size_limit_and_missing_file(self):
        headers = {"doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "docx": b"PK\x03\x04document", "pdf": b"%PDF-1.4\n"}
        for extension, content in headers.items():
            form = TrainingLogTemplateForm(
                {"name": "模板", "training_cycle": self.cycle1.pk, "order": 0},
                {"file": SimpleUploadedFile(f"template.{extension}", content)},
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.fields["file"].widget.attrs["accept"], ".doc,.docx,.pdf")
        upload = self.upload()
        upload.size = 21 * 1024 * 1024
        form = TrainingLogTemplateForm({"name": "过大", "training_cycle": self.cycle1.pk, "order": 0},
                                       {"file": upload})
        self.assertFalse(form.is_valid())
        self.assertIn("20MB", str(form.errors["file"]))
        with self.assertRaisesMessage(ValidationError, "请上传模板文件"):
            save_log_template(TrainingLogTemplate(name="空模板", training_cycle=self.cycle1), actor=self.manager)
