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
from django.utils import timezone

from accounts.models import UserProfile

from .log_management import (
    can_manage_log_deletions,
    confirm_log_deletion,
    filter_training_logs,
    preview_log_deletion,
)
from .models import TrainingCycleMember, TrainingLog, TrainingPlan
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
        self.enterContext(patch("django.utils.timezone.localdate", return_value=date(2026, 2, 28)))
        self.period = self.cycle(end_date=date(2026, 2, 28))
        self.other_period = self.cycle("C2")
        self.plan = self.create_plan(self.period, date(2026, 1, 2), date(2026, 2, 28))
        self.other_plan = self.create_plan(self.other_period, date(2026, 1, 1), date(2026, 1, 31))
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

    def create_plan(self, cycle, start, end, **kwargs):
        return TrainingPlan.objects.create(
            training_cycle=cycle, title=kwargs.pop("title", "训练计划"), start_date=start, end_date=end,
            created_by=self.manager, published_at=timezone.now(), schedule_published_at=timezone.now(), **kwargs,
        )

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

    def test_search_full_name_pinyin_student_id_content_and_filename(self):
        self.log.document = "logs/C1/2026/01/routing-notes.pdf"
        self.log.save()
        for query, expected in (
            ("张三", {self.log.pk, self.other_log.pk}),
            ("zhangsan", {self.log.pk, self.other_log.pk}),
            ("candidate", set()),
            ("20261001", {self.log.pk, self.other_log.pk}),
            ("路由实验", {self.log.pk}), ("网络丢包", {self.log.pk}),
            ("routing-notes.pdf", {self.log.pk}),
        ):
            with self.subTest(query=query):
                self.assertEqual(self.ids(self.client.get(self.url, {"q": query, "plan": "all"})), expected)

    def test_plan_date_range_and_current_cycle_identity_filters(self):
        response = self.client.get(self.url, {
            "plan": self.plan.pk, "date_from": "2026-01-02", "date_to": "2026-01-03", "member_role": "coach",
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
        response = self.client.get(self.url, {"plan": self.plan.pk, "member_role": "coach"})
        self.assertEqual(self.ids(response), {self.log.pk, self.coach_log.pk})
        self.assertContains(self.client.get(self.url, {"plan": self.other_plan.pk}), "未关联")
        for invalid in ({"date_from": "invalid"}, {"date_from": "2026-01-04", "date_to": "2026-01-01"},
                        {"member_role": "invalid"}, {"plan": "not-a-number"}):
            with self.subTest(invalid=invalid):
                response = self.client.get(self.url, invalid)
                self.assertEqual(self.ids(response), set())
                self.assertTrue(response.context["filter_form"].errors)

    def test_default_latest_ongoing_plan_and_training_date_order(self):
        self.create_plan(self.other_period, date(2026, 1, 1), date(2026, 1, 31))
        older = self.create_plan(self.period, date(2026, 1, 1), date(2026, 2, 28), title="较早开始")
        self.create_plan(self.period, date(2026, 2, 28), date(2026, 2, 28), status=TrainingPlan.Status.ARCHIVED)
        self.create_plan(self.period, date(2026, 2, 28), date(2026, 2, 28), status=TrainingPlan.Status.COMPLETED)
        self.log.save()
        response = self.client.get(self.url)
        self.assertEqual(response.context["filter_form"].default_plan, self.plan)
        self.assertEqual([row.record.pk for row in response.context["table"].rows], [self.coach_log.pk, self.log.pk])
        self.assertEqual(self.ids(self.client.get(self.url, {"plan": older.pk})), {self.log.pk, self.coach_log.pk})
        self.assertEqual(self.ids(self.client.get(self.url, {"plan": self.other_plan.pk})), {self.other_log.pk})
        with patch("django.utils.timezone.localdate", return_value=date(2026, 3, 1)):
            response = self.client.get(self.url)
            self.assertEqual(self.ids(response), set())
            self.assertContains(response, "暂无进行中的训练计划")
            self.assertEqual(self.ids(self.client.get(self.url, {"plan": "all"})), {self.log.pk, self.coach_log.pk, self.other_log.pk})

    def test_search_respects_visibility_and_htmx_partial(self):
        self.grant(self.author, "view_traininglog", "delete_traininglog")
        self.client.force_login(self.author)
        self.assertEqual(self.ids(self.client.get(self.url, {"q": "李四"})), set())
        response = self.client.get(self.url)
        self.assertNotContains(response, "data-row-selection")
        self.assertContains(response, f'data-modal-target="delete-log-{self.log.pk}"')
        self.assertEqual(self.client.post(reverse("training:log_delete", args=[self.coach_log.pk])).status_code, 404)
        self.assertFalse(can_manage_log_deletions(self.author))
        self.assertEqual(self.client.post(self.url, {"logs": [self.log.pk], "operation": "delete",
                                                    "selection": "selected"}).status_code, 403)
        self.client.force_login(self.manager)
        response = self.client.get(self.url, {"q": "张三"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "data-bulk-list")
        self.assertNotContains(response, "<!DOCTYPE")
        self.assertContains(response, "张三")

    def test_single_delete_uses_modal_outside_bulk_form_and_shows_alert(self):
        query = urlencode({"plan": "all"})
        response = self.client.get(self.url + "?" + query)
        soup = BeautifulSoup(response.content, "html.parser")
        selections = soup.select("input[data-row-selection]")
        self.assertEqual(len(selections), 2)
        self.assertTrue(all(field.get("name") == "logs" for field in selections))
        self.assertEqual({int(field["value"]) for field in selections},
                         {self.log.pk, self.coach_log.pk})
        self.assertIsNotNone(soup.select_one("input[data-select-page]"))
        delete = soup.select_one(f'button[data-modal-target="delete-log-{self.log.pk}"]')
        self.assertIsNotNone(delete)
        for css in ("btn", "btn-soft", "btn-error", "btn-xs"):
            self.assertIn(css, delete["class"])
        for label in ("查看", "编辑"):
            self.assertIn("btn-xs", soup.find("a", string=label)["class"])
        self.assertFalse(any(form.find("form") for form in soup.find_all("form")))
        dialog = soup.select_one(f"dialog#delete-log-{self.log.pk}")
        self.assertIsNone(dialog.find_parent("form"))
        self.assertIsNotNone(dialog.select_one('form[method="post"] input[name="csrfmiddlewaretoken"]'))
        url = reverse("training:log_delete", args=[self.log.pk]) + "?" + urlencode({"return_query": query})
        self.assertEqual(dialog.select_one('form[method="post"]')["action"], url)
        self.assertIsNone(soup.select_one(f"dialog#delete-log-{self.other_log.pk}"))
        response = self.client.get(url)
        self.assertContains(response, "确认删除训练日志")
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual(soup.find("a", string="取消")["href"], self.url + "?" + query)
        response = self.client.post(url, follow=True)
        self.assertRedirects(response, self.url + "?" + query)
        alert = BeautifulSoup(response.content, "html.parser").select_one(".alert-success")
        self.assertIsNotNone(alert)
        self.assertIn("已删除训练日志及其附件", alert.get_text())
        self.assertFalse(TrainingLog.objects.filter(pk=self.log.pk).exists())

    def test_preview_fixed_selection_and_confirmation_preserve_filters(self):
        query = urlencode({"q": "张三", "plan": self.plan.pk, "page": 1})
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
        outside = TrainingLog.objects.filter(training_cycle=self.period).exclude(pk__in=page_ids).first()
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

    def test_ended_plan_cannot_be_deleted_by_staff_with_delete_all_permission(self):
        self.manager.is_staff = True
        self.manager.save(update_fields=["is_staff"])
        pk = self.other_log.pk
        for route in ("training:log_delete", "admin:training_traininglog_delete"):
            url = reverse(route, args=[pk])
            expected = 404 if route.startswith("training:") else 403
            self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, expected)
        self.assertEqual(self.client.post(reverse("admin:training_traininglog_changelist"), {
            "action": "delete_selected", "_selected_action": [pk], "post": "yes",
        }).status_code, 403)
        self.assertTrue(TrainingLog.objects.filter(pk=pk).exists())
        self.assertEqual(self.client.post(reverse("admin:training_traininglog_changelist"), {
            "action": "delete_selected", "_selected_action": [self.log.pk], "post": "yes",
        }).status_code, 302)
        self.assertFalse(TrainingLog.objects.filter(pk=self.log.pk).exists())

    def test_superuser_can_delete_ended_and_unmatched_logs(self):
        self.manager.is_staff = self.manager.is_superuser = True
        self.manager.save(update_fields=["is_staff", "is_superuser"])
        historical = self.other_log
        admin_single = self.create_log(self.author, date(2026, 1, 5), cycle=self.other_period)
        admin_batch = self.create_log(self.author, date(2026, 1, 6), cycle=self.other_period)
        unmatched = self.create_log(self.author, date(2026, 1, 1))
        query = {"plan": self.other_plan.pk}

        response = self.client.get(self.url, query)
        self.assertContains(response, f'data-modal-target="delete-log-{historical.pk}"')
        self.assertEqual(self.client.post(reverse("training:log_delete", args=[historical.pk])).status_code, 302)

        all_logs_url = self.url + "?plan=all"
        preview = self.client.post(all_logs_url, {"selection": "selected", "operation": "delete", "logs": [unmatched.pk]})
        self.assertEqual(preview.status_code, 200)
        confirm = self.client.post(all_logs_url, {"stage": "confirm", "token": preview.context["token"]})
        self.assertRedirects(confirm, all_logs_url)

        admin_delete_url = reverse("admin:training_traininglog_delete", args=[admin_single.pk])
        self.assertEqual(self.client.post(admin_delete_url, {"post": "yes"}).status_code, 302)
        admin_list_url = reverse("admin:training_traininglog_changelist")
        self.assertEqual(self.client.post(admin_list_url, {
            "action": "delete_selected", "_selected_action": [admin_batch.pk], "post": "yes",
        }).status_code, 302)
        self.assertFalse(TrainingLog.objects.filter(pk__in=[historical.pk, unmatched.pk, admin_single.pk, admin_batch.pk]).exists())

    def test_confirmation_rechecks_plan_end_and_protects_overlap(self):
        preview = self.preview()
        with patch("django.utils.timezone.localdate", return_value=date(2026, 3, 1)):
            with self.assertRaises(ValidationError):
                confirm_log_deletion(actor=self.manager, token=preview["token"])
        historical = self.create_plan(self.period, date(2026, 1, 1), date(2026, 1, 2))
        url = reverse("training:log_delete", args=[self.log.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        historical.schedule_published_at = None
        historical.save(update_fields=["schedule_published_at"])
        self.assertEqual(self.client.post(url).status_code, 404)
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
