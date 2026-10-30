from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile

from .member_management import confirm_member_add, prepare_member_add, preview_member_add
from .models import TrainingCycle, TrainingCycleMember
from .tests import TrainingFixtureMixin, User


class MemberManagementTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.manager = User.objects.create_superuser("manager", password="test")
        self.user = User.objects.create_user("candidate", last_name="张", first_name="三")
        self.cycle_obj = self.cycle()
        self.bind(self.cycle_obj)
        self.cycle_obj.status = TrainingCycle.Status.ACTIVE
        self.cycle_obj.save()
        self.url = reverse("training:cycle_members", args=[self.cycle_obj.pk])
        self.client.force_login(self.manager)

    def preview(self, *, is_current=False):
        parameters = prepare_member_add(actor=self.manager, cycle=self.cycle_obj,
                                        ids=[self.user.pk], return_query="mode=add&q=candidate&page=2")
        return preview_member_add(actor=self.manager, cycle=self.cycle_obj, token=parameters["token"],
                                  role="competitor", is_current=is_current)

    def test_candidates_search_filter_pagination_and_page_selection(self):
        group = Group.objects.create(name="选手")
        self.user.groups.add(group)
        UserProfile.objects.create(user=self.user, join_date=date(2026, 1, 2), student_id="202601")
        member = User.objects.create_user("existing")
        TrainingCycleMember.objects.create(user=member, training_cycle=self.cycle_obj, role="coach")
        User.objects.create_user("inactive", is_active=False)
        response = self.client.get(self.url, {"mode": "add", "q": "张三", "role": group.pk})
        self.assertContains(response, "张三")
        self.assertContains(response, "2026-01-02")
        self.assertEqual([row.record.pk for row in response.context["table"].rows], [self.user.pk])
        self.assertNotContains(response, 'value="%s" aria-label="选择' % member.pk)
        response = self.client.get(self.url, {"mode": "add", "q": "202601"})
        self.assertEqual(len(response.context["table"].rows), 1)
        response = self.client.get(self.url, {"mode": "add", "q": "candidate"}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "data-bulk-list")
        self.assertNotContains(response, "<!DOCTYPE")
        invalid = self.client.post(self.url + "?mode=add&q=does-not-match", {
            "operation": "add", "selection": "selected", "users": [self.user.pk],
        }, follow=True)
        self.assertContains(invalid, "不属于当前筛选页")
        for index in range(26):
            User.objects.create_user(f"page{index}")
        response = self.client.get(self.url, {"mode": "add"})
        self.assertEqual(len(response.context["table"].page.object_list), 25)
        page2 = self.client.get(self.url, {"mode": "add", "page": 2})
        self.assertTrue(page2.context["table"].page.object_list)
        last = self.client.get(self.url, {"mode": "add", "page": 999})
        self.assertEqual(last.context["table"].page.number, 2)
        self.assertEqual(self.client.get(self.url, {"mode": "add", "role": "invalid"}).status_code, 400)

    def test_existing_members_search_identity_and_current_filter(self):
        TrainingCycleMember.objects.create(user=self.user, training_cycle=self.cycle_obj,
                                           role="competitor", is_current=True)
        response = self.client.get(self.url, {"q": "张三", "member_role": "competitor", "current": "1"})
        self.assertContains(response, "张三")
        self.assertNotContains(response, "data-row-selection")
        response = self.client.get(self.url, {"member_role": "coach"})
        self.assertEqual(len(response.context["table"].rows), 0)

    def test_confirmation_rejects_state_change_tampering_expiry_and_replay(self):
        preview = self.preview(is_current=True)
        with self.assertRaises(ValidationError):
            confirm_member_add(actor=self.manager, cycle=self.cycle_obj, token=preview["token"] + "x")
        with patch("django.core.signing.time.time", return_value=9999999999):
            with self.assertRaisesMessage(ValidationError, "过期"):
                confirm_member_add(actor=self.manager, cycle=self.cycle_obj, token=preview["token"])
        self.user.is_active = False
        self.user.save()
        with self.assertRaisesMessage(ValidationError, "停用"):
            confirm_member_add(actor=self.manager, cycle=self.cycle_obj, token=preview["token"])
        self.user.is_active = True
        self.user.save()
        query = confirm_member_add(actor=self.manager, cycle=self.cycle_obj, token=preview["token"])
        self.assertEqual(query, "mode=add&q=candidate&page=2")
        self.assertTrue(TrainingCycleMember.objects.get(user=self.user).is_current)
        with self.assertRaisesMessage(ValidationError, "已加入"):
            confirm_member_add(actor=self.manager, cycle=self.cycle_obj, token=preview["token"])

    def test_confirmation_rechecks_permissions_and_current_membership(self):
        preview = self.preview(is_current=True)
        self.manager.is_superuser = False
        self.manager.save()
        with self.assertRaises(PermissionDenied):
            confirm_member_add(actor=self.manager, cycle=self.cycle_obj, token=preview["token"])
        self.manager.is_superuser = True
        self.manager.save()
        other = self.cycle("OTHER")
        TrainingCycleMember.objects.create(user=self.user, training_cycle=other, role="coach")
        with self.assertRaisesMessage(ValidationError, "状态已变化"):
            confirm_member_add(actor=self.manager, cycle=self.cycle_obj, token=preview["token"])

    def test_view_only_user_has_no_bulk_controls_and_cannot_post(self):
        viewer = User.objects.create_user("viewer")
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label="training",
                                                           codename="view_trainingcyclemember"))
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(self.url), "添加成员")
        self.assertEqual(self.client.get(self.url + "?mode=add").status_code, 403)
        self.assertEqual(self.client.post(self.url, {"stage": "confirm", "token": self.preview()["token"]}).status_code, 403)
