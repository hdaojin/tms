from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .admin import CycleMemberAdminForm
from .forms import TrainingLogForm
from .models import TaskExecution, TrainingCycle, TrainingCycleMember, TrainingLog, TrainingPlan, TrainingTask
from .services import remove_cycle_member, save_cycle_member, save_training_log
from .tests import TrainingFixtureMixin, User


class CycleMemberTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        self.enterContext(override_settings(PRIVATE_MEDIA_ROOT=media.name))
        self.user = User.objects.create_user("member", last_name="测", first_name="试")
        self.manager = User.objects.create_user("manager")
        self.cycle1 = self.active_cycle("C1")
        self.cycle2 = self.active_cycle("C2")
        self.member = TrainingCycleMember.objects.create(
            user=self.user, training_cycle=self.cycle1, role="competitor", is_current=True
        )
        self.other = TrainingCycleMember.objects.create(user=self.user, training_cycle=self.cycle2, role="competitor")
        self.client.force_login(self.manager)

    def active_cycle(self, code):
        cycle = self.cycle(code)
        self.bind(cycle)
        cycle.status = TrainingCycle.Status.ACTIVE
        cycle.save()
        return cycle

    def grant(self, *codes):
        self.manager.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="training", codename__in=codes
        ))

    def data(self, **kwargs):
        return {"training_cycle": self.cycle1.pk, "training_date": "2026-01-02", "topic": "日志", **kwargs}

    def test_database_unique_and_atomic_switch_rollback(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TrainingCycleMember.objects.filter(pk=self.other.pk).update(is_current=True)
        self.other.is_current = True
        with patch.object(TrainingCycleMember, "save", side_effect=RuntimeError("失败")):
            with self.assertRaises(RuntimeError):
                save_cycle_member(self.other)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_current)
        save_cycle_member(self.other)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_current)
        self.assertEqual(TrainingCycleMember.objects.get(user=self.user, is_current=True), self.other)

    def test_inactive_cycle_cannot_be_set_current(self):
        self.cycle2.status = TrainingCycle.Status.COMPLETED
        self.cycle2.save()
        self.other.training_cycle = self.cycle2
        self.other.is_current = True
        with self.assertRaisesMessage(ValidationError, "只有进行中"):
            save_cycle_member(self.other)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_current)

    def test_permissions_bulk_add_and_change_current(self):
        url = reverse("training:cycle_members", args=[self.cycle2.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.grant("view_trainingcyclemember")
        self.assertContains(self.client.get(url), "周期成员")
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.grant("add_trainingcyclemember")
        new_user = User.objects.create_user("new")
        url += "?mode=add"
        parameters = self.client.post(url, {"users": [new_user.pk], "operation": "add", "selection": "selected"})
        self.assertEqual(parameters.status_code, 200)
        self.assertFalse(TrainingCycleMember.objects.filter(user=new_user).exists())
        preview = self.client.post(url, {"stage": "parameters", "token": parameters.context["token"],
                                         "role": "coach", "is_current": "on"})
        self.assertFalse(TrainingCycleMember.objects.filter(user=new_user).exists())
        response = self.client.post(url, {"stage": "confirm", "token": preview.context["token"]})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TrainingCycleMember.objects.get(user=new_user).is_current)
        edit = reverse("training:member_edit", args=[self.cycle2.pk, self.other.pk])
        self.assertEqual(self.client.post(edit, {"role": "competitor", "is_current": "on"}).status_code, 403)
        self.grant("change_trainingcyclemember")
        self.assertContains(self.client.get(edit), "替换")
        self.assertEqual(self.client.post(edit, {"role": "competitor", "is_current": "on"}).status_code, 302)
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_current)

    def test_bulk_add_rolls_back_if_any_member_fails(self):
        self.grant("view_trainingcyclemember", "add_trainingcyclemember", "change_trainingcyclemember")
        users = [User.objects.create_user(f"bulk{i}") for i in range(2)]
        url = reverse("training:cycle_members", args=[self.cycle2.pk])
        original = TrainingCycleMember.save

        def fail_second(member, *args, **kwargs):
            if member.user_id == users[1].pk:
                raise ValidationError("第二项失败")
            return original(member, *args, **kwargs)

        url += "?mode=add"
        parameters = self.client.post(url, {"users": [user.pk for user in users],
                                             "operation": "add", "selection": "selected"})
        preview = self.client.post(url, {"stage": "parameters", "token": parameters.context["token"],
                                         "role": "coach", "is_current": "on"})
        with patch.object(TrainingCycleMember, "save", fail_second):
            self.assertContains(self.client.post(url, {
                "stage": "confirm", "token": preview.context["token"],
            }, follow=True), "第二项失败")
        self.assertFalse(TrainingCycleMember.objects.filter(user__in=users).exists())

    def test_task_and_log_protect_members(self):
        plan = TrainingPlan.objects.create(training_cycle=self.cycle1, title="计划",
                                           start_date=date(2026, 1, 1), end_date=date(2026, 1, 31), created_by=self.manager)
        task = TrainingTask.objects.create(training_plan=plan, title="任务", planned_date=date(2026, 1, 2),
                                           created_by=self.manager)
        TaskExecution.objects.create(training_task=task, user=self.user)
        self.member.role = "coach"
        with self.assertRaisesMessage(ValidationError, "不能改变身份"):
            save_cycle_member(self.member)
        with self.assertRaisesMessage(ValidationError, "任务关联"):
            remove_cycle_member(self.member)
        TrainingLog.objects.create(training_cycle=self.cycle2, author=self.user,
                                   training_date=date(2026, 1, 2), topic="历史")
        with self.assertRaisesMessage(ValidationError, "训练日志"):
            remove_cycle_member(self.other)
        self.grant("view_trainingcyclemember", "delete_trainingcyclemember")
        url = reverse("training:member_delete", args=[self.cycle2.pk, self.other.pk])
        self.assertContains(self.client.get(url), "不能移除")
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertTrue(TrainingCycleMember.objects.filter(pk=self.other.pk).exists())

    def test_admin_switch_and_protection(self):
        self.manager.is_staff = self.manager.is_superuser = True
        self.manager.save()
        url = reverse("admin:training_trainingcyclemember_change", args=[self.other.pk])
        form = CycleMemberAdminForm({"role": "coach", "is_current": "on"}, instance=self.other)
        # Admin excludes its readonly identity fields from the actual form.
        form.fields.pop("user")
        form.fields.pop("training_cycle")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(self.client.post(url, {"role": "coach", "is_current": "on", "_save": "保存"}).status_code, 302)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_current)
        TrainingLog.objects.create(training_cycle=self.cycle2, author=self.user,
                                   training_date=date(2026, 1, 2), topic="保留成员")
        delete_url = reverse("admin:training_trainingcyclemember_delete", args=[self.other.pk])
        self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 403)
        self.assertTrue(TrainingCycleMember.objects.filter(pk=self.other.pk).exists())

    def test_admin_add_without_change_cannot_set_current(self):
        self.manager.is_staff = True
        self.manager.save()
        self.grant("view_trainingcyclemember", "add_trainingcyclemember")
        new_user = User.objects.create_user("admin-added")
        response = self.client.post(reverse("admin:training_trainingcyclemember_add"), {
            "user": new_user.pk, "training_cycle": self.cycle2.pk, "role": "coach", "is_current": "on",
            "_save": "保存",
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TrainingCycleMember.objects.get(user=new_user).is_current)

    @patch("django.utils.timezone.localdate", return_value=date(2026, 1, 2))
    def test_service_rechecks_status_after_form_validation(self, mock_today):
        form = TrainingLogForm(self.data(), {"document": SimpleUploadedFile("log.pdf", b"%PDF-1.4\ntraining")},
                               author=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.cycle1.status = TrainingCycle.Status.COMPLETED
        self.cycle1.save()
        with self.assertRaisesMessage(ValidationError, "当前周期"):
            form.save()

    def test_unused_current_member_can_be_removed(self):
        self.grant("view_trainingcyclemember", "delete_trainingcyclemember")
        response = self.client.post(reverse("training:member_delete", args=[self.cycle1.pk, self.member.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TrainingCycleMember.objects.filter(user=self.user, is_current=True).exists())

    @patch("django.utils.timezone.localdate", return_value=date(2026, 1, 2))
    def test_daily_ignores_forged_cycle_and_service_rechecks(self, mock_today):
        form = TrainingLogForm(self.data(training_cycle=self.cycle2.pk),
                               {"document": SimpleUploadedFile("log.pdf", b"%PDF-1.4\ntraining")}, author=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().training_cycle_id, self.cycle1.pk)
        self.other.is_current = True
        save_cycle_member(self.other)
        log = TrainingLog(training_cycle=self.cycle1, author=self.user, training_date=date(2026, 1, 1), topic="伪造")
        log.document = SimpleUploadedFile("log.pdf", b"%PDF-1.4\ntraining")
        with self.assertRaisesMessage(ValidationError, "当前周期"):
            save_training_log(log, [])

    def test_backfill_membership_status_dates_and_permission(self):
        self.cycle2.status = TrainingCycle.Status.COMPLETED
        self.cycle2.save()
        form = TrainingLogForm(self.data(training_cycle=self.cycle2.pk),
                               {"document": SimpleUploadedFile("log.pdf", b"%PDF-1.4\ntraining")},
                               author=self.user, backfill=True)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_current)
        self.assertFalse(TrainingLogForm(self.data(training_date="2026-02-01"), author=self.user).is_valid())
        self.cycle2.status = TrainingCycle.Status.ARCHIVED
        self.cycle2.save()
        self.assertFalse(TrainingLogForm(self.data(training_cycle=self.cycle2.pk),
                                         author=self.user, backfill=True).is_valid())
        unjoined = self.active_cycle("UNJOINED")
        self.assertFalse(TrainingLogForm(self.data(training_cycle=unjoined.pk),
                                         author=self.user, backfill=True).is_valid())
        self.assertEqual(self.client.get(reverse("training:log_backfill")).status_code, 403)
        self.grant("add_traininglog")
        self.assertEqual(self.client.get(reverse("training:log_backfill")).status_code, 200)

    def test_missing_or_completed_current_blocks_creation_without_fallback(self):
        self.cycle1.status = TrainingCycle.Status.COMPLETED
        self.cycle1.save()
        form = TrainingLogForm(self.data(), author=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("联系管理员", str(form.errors))
        self.assertIsNone(form.current_cycle)
        TrainingCycleMember.objects.filter(pk=self.member.pk).update(is_current=False)
        self.assertFalse(TrainingLogForm(self.data(), author=self.user).is_valid())

    def test_legacy_text_edit_retains_cycle_without_membership_or_date_validation(self):
        log = TrainingLog.objects.create(training_cycle=self.cycle1, author=self.manager,
                                         training_date=date(2025, 1, 1), topic="历史异常")
        form = TrainingLogForm(self.data(training_cycle=self.cycle2.pk, training_date="2025-01-01", summary="更新"),
                               author=self.manager, instance=log)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        log.refresh_from_db()
        self.assertEqual(log.training_cycle_id, self.cycle1.pk)
        self.assertEqual(log.summary, "更新")
