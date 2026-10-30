from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db.models.signals import post_delete
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile

from .log_management import (
    can_manage_log_deletions,
    confirm_log_deletion,
    filter_training_logs,
    preview_log_deletion,
)
from .models import TrainingCycleMember, TrainingLog
from .tests import TrainingFixtureMixin, User


class TrainingLogListManagementTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        self.enterContext(override_settings(PRIVATE_MEDIA_ROOT=media.name))
        self.manager = User.objects.create_user("manager")
        self.author = User.objects.create_user("candidate", last_name="张", first_name="三")
        self.coach = User.objects.create_user("coach", last_name="李", first_name="四")
        UserProfile.objects.create(user=self.author, student_id="20261001")
        self.period = self.cycle()
        self.other_period = self.cycle("C2")
        self.membership = TrainingCycleMember.objects.create(
            user=self.author, training_cycle=self.period, role="competitor",
        )
        TrainingCycleMember.objects.create(user=self.coach, training_cycle=self.period, role="coach")
        self.log = self.create_log(self.author, date(2026, 1, 2), topic="路由实验", summary="排查网络丢包")
        self.coach_log = self.create_log(self.coach, date(2026, 1, 3), topic="指导记录")
        self.other_log = self.create_log(self.author, date(2026, 1, 4), cycle=self.other_period)
        self.grant(self.manager, "view_traininglog", "view_all_traininglog", "change_traininglog",
                   "change_all_traininglog", "delete_traininglog", "delete_all_traininglog")
        self.client.force_login(self.manager)
        self.url = reverse("training:log_list")

    def grant(self, user, *codes):
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="training", codename__in=codes,
        ))
        for key in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            user.__dict__.pop(key, None)

    def create_log(self, author, day, *, cycle=None, **kwargs):
        return TrainingLog.objects.create(author=author, training_cycle=cycle or self.period,
                                           training_date=day, **kwargs)

    def ids(self, response):
        self.assertEqual(response.status_code, 200)
        return {row.record.pk for row in response.context["table"].rows}

    def preview(self, logs=None, query=""):
        return preview_log_deletion(actor=self.manager, ids=[log.pk for log in (logs or [self.log])],
                                     return_query=query)

    def attach_file(self, log):
        log.document.save(f"log-{log.pk}.txt", ContentFile(b"training log"), save=True)
        return log.document.storage, log.document.name

    def test_search_full_name_username_student_id_content_and_filename(self):
        self.log.document = "logs/C1/2026/01/routing-notes.pdf"
        self.log.save()
        for query, expected in (
            ("张三", {self.log.pk, self.other_log.pk}),
            ("candidate", {self.log.pk, self.other_log.pk}),
            ("20261001", {self.log.pk, self.other_log.pk}),
            ("路由实验", {self.log.pk}), ("网络丢包", {self.log.pk}),
            ("routing-notes.pdf", {self.log.pk}),
        ):
            with self.subTest(query=query):
                self.assertEqual(self.ids(self.client.get(self.url, {"q": query})), expected)

    def test_cycle_date_range_and_current_cycle_identity_filters(self):
        response = self.client.get(self.url, {
            "cycle": self.period.pk, "date_from": "2026-01-02", "date_to": "2026-01-03", "member_role": "coach",
        })
        self.assertEqual(self.ids(response), {self.coach_log.pk})
        self.assertContains(response, "周期身份")
        self.assertContains(response, "教练")
        self.assertTemplateUsed(response, "components/list_filter_toolbar.html")
        soup = BeautifulSoup(response.content, "html.parser")
        toolbar = soup.select_one("form[hx-get]")
        self.assertIsNone(toolbar.find("button", string="筛选"))
        self.assertEqual(len(toolbar.select("input.list-filter-date")), 2)
        self.assertEqual(toolbar.select_one('input[name="date_from"]')["value"], "2026-01-02")
        self.assertIn("change from:.list-filter-date", toolbar["hx-trigger"])
        self.assertEqual(self.ids(self.client.get(self.url, {"date_from": "2026-01-03", "date_to": "2026-01-03"})),
                         {self.coach_log.pk})
        self.membership.role = "coach"
        self.membership.save()
        response = self.client.get(self.url, {"cycle": self.period.pk, "member_role": "coach"})
        self.assertEqual(self.ids(response), {self.log.pk, self.coach_log.pk})
        self.assertContains(self.client.get(self.url), "未关联")
        for invalid in ({"date_from": "invalid"}, {"date_from": "2026-01-04", "date_to": "2026-01-01"},
                        {"member_role": "invalid"}, {"cycle": "not-a-number"}):
            with self.subTest(invalid=invalid):
                response = self.client.get(self.url, invalid)
                self.assertEqual(self.ids(response), set())
                self.assertTrue(response.context["filter_form"].errors)

    def test_search_respects_visibility_and_htmx_partial(self):
        self.grant(self.author, "view_traininglog", "delete_traininglog")
        self.client.force_login(self.author)
        self.assertEqual(self.ids(self.client.get(self.url, {"q": "李四"})), set())
        response = self.client.get(self.url)
        self.assertNotContains(response, "data-row-selection")
        self.assertNotContains(response, ">删除</a>")
        self.assertFalse(can_manage_log_deletions(self.author))
        self.assertEqual(self.client.post(self.url, {"logs": [self.log.pk], "operation": "delete",
                                                    "selection": "selected"}).status_code, 403)
        self.client.force_login(self.manager)
        response = self.client.get(self.url, {"q": "张三"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "data-bulk-list")
        self.assertNotContains(response, "<!DOCTYPE")
        self.assertContains(response, "张三")

    def test_single_delete_button_uses_matching_style_and_confirmation_page(self):
        response = self.client.get(self.url)
        soup = BeautifulSoup(response.content, "html.parser")
        selections = soup.select("input[data-row-selection]")
        self.assertEqual(len(selections), 3)
        self.assertTrue(all(field.get("name") == "logs" for field in selections))
        self.assertEqual({int(field["value"]) for field in selections},
                         {self.log.pk, self.coach_log.pk, self.other_log.pk})
        self.assertIsNotNone(soup.select_one("input[data-select-page]"))
        delete = soup.find("a", string="删除")
        self.assertIsNotNone(delete)
        for css in ("btn", "btn-soft", "btn-error", "btn-xs"):
            self.assertIn(css, delete["class"])
        for label in ("查看", "编辑"):
            self.assertIn("btn-xs", soup.find("a", string=label)["class"])
        self.assertFalse(any(form.find("form") for form in soup.find_all("form")))
        query = urlencode({"q": "张三", "cycle": self.period.pk})
        url = reverse("training:log_delete", args=[self.log.pk]) + "?" + urlencode({"return_query": query})
        response = self.client.get(url)
        self.assertContains(response, "确认删除训练日志")
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual(soup.find("a", string="取消")["href"], self.url + "?" + query)
        response = self.client.post(url)
        self.assertRedirects(response, self.url + "?" + query)
        self.assertFalse(TrainingLog.objects.filter(pk=self.log.pk).exists())

    def test_preview_fixed_selection_and_confirmation_preserve_filters(self):
        query = urlencode({"q": "张三", "cycle": self.period.pk, "page": 1})
        url = self.url + "?" + query
        response = self.client.post(url, {"selection": "selected", "operation": "delete", "logs": [self.log.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TrainingLog.objects.filter(pk=self.log.pk).exists())
        self.assertContains(response, "张三")
        response = self.client.post(url, {"stage": "confirm", "token": response.context["token"]})
        self.assertRedirects(response, self.url + "?" + query)
        self.assertFalse(TrainingLog.objects.filter(pk=self.log.pk).exists())
        self.assertTrue(TrainingLog.objects.filter(pk=self.other_log.pk).exists())

    def test_cannot_select_outside_filter_or_current_page_or_all_matching(self):
        url = self.url + "?q=" + "张三"
        self.client.post(url, {"selection": "selected", "operation": "delete", "logs": [self.coach_log.pk]})
        self.assertTrue(TrainingLog.objects.filter(pk=self.coach_log.pk).exists())
        self.client.post(self.url, {"selection": "all", "operation": "delete"})
        self.assertEqual(TrainingLog.objects.count(), 3)
        for day in range(1, 29):
            self.create_log(self.coach, date(2026, 2, day))
        response = self.client.get(self.url)
        page_ids = {row.record.pk for row in response.context["table"].page.object_list}
        outside = TrainingLog.objects.exclude(pk__in=page_ids).first()
        self.assertIsNotNone(outside)
        self.client.post(self.url, {"selection": "selected", "operation": "delete", "logs": [outside.pk]})
        self.assertTrue(TrainingLog.objects.filter(pk=outside.pk).exists())

    def test_service_rejects_signature_expiry_and_changed_log(self):
        preview = self.preview()
        with self.assertRaises(ValidationError):
            confirm_log_deletion(actor=self.manager, token=preview["token"] + "x")
        with patch("django.core.signing.time.time", return_value=9999999999):
            with self.assertRaises(ValidationError):
                confirm_log_deletion(actor=self.manager, token=preview["token"])
        self.log.summary = "预览后的修改"
        self.log.save()
        with self.assertRaises(ValidationError):
            confirm_log_deletion(actor=self.manager, token=preview["token"])
        self.assertTrue(TrainingLog.objects.filter(pk=self.log.pk).exists())

    def test_service_rechecks_permission_after_preview(self):
        preview = self.preview()
        self.manager.user_permissions.remove(Permission.objects.get(
            content_type__app_label="training", codename="delete_all_traininglog",
        ))
        with self.assertRaises(PermissionDenied):
            confirm_log_deletion(actor=self.manager, token=preview["token"])
        self.assertTrue(TrainingLog.objects.filter(pk=self.log.pk).exists())

    def test_delete_cleans_files_after_commit_and_failed_batch_rolls_back(self):
        storage, first_name = self.attach_file(self.log)
        _storage, second_name = self.attach_file(self.coach_log)
        preview = self.preview([self.log, self.coach_log])

        def fail_delete(sender, instance, **kwargs):
            if instance.pk == self.log.pk:
                raise ValidationError("模拟删除失败")

        post_delete.connect(fail_delete, sender=TrainingLog, weak=False)
        try:
            with self.captureOnCommitCallbacks(execute=True), self.assertRaises(ValidationError):
                confirm_log_deletion(actor=self.manager, token=preview["token"])
        finally:
            post_delete.disconnect(fail_delete, sender=TrainingLog)
        self.assertTrue(TrainingLog.objects.filter(pk=self.log.pk).exists())
        self.assertTrue(TrainingLog.objects.filter(pk=self.coach_log.pk).exists())
        self.assertTrue(storage.exists(first_name))
        self.assertTrue(storage.exists(second_name))
        with self.captureOnCommitCallbacks(execute=True):
            confirm_log_deletion(actor=self.manager, token=preview["token"])
            self.assertTrue(storage.exists(first_name))
        self.assertFalse(storage.exists(first_name))
        self.assertFalse(storage.exists(second_name))

    def test_invalid_filter_service_rejects_instead_of_widening_scope(self):
        with self.assertRaises(ValidationError):
            filter_training_logs(self.manager, {"member_role": "invalid"})
