from datetime import datetime, timezone as utc
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.navigation import get_section_items

from .models import PersonalTrainingTask, TaskExecution, TrainingBoardPlan, TrainingTask, TrainingTaskCoach
from .test_process_refactor import ProcessFixture


class TrainingBoardTests(ProcessFixture, TestCase):
    def test_public_board_has_a_training_menu_entry(self):
        menu = get_section_items("training", AnonymousUser())
        self.assertIn(reverse("training:board"), [item.resolved_url for group in menu for item in group.children])

    def test_competitors_see_only_own_effective_assignments_and_personal_tasks(self):
        first = self.task(title="选手甲的任务", assign_all=False, competitors=[self.student.pk])
        second = self.task(title="选手乙的任务", assign_all=False, competitors=[self.student2.pk])
        first.executions.filter(user=self.student).update(status=TaskExecution.Status.IN_PROGRESS)
        PersonalTrainingTask.objects.create(
            training_plan=self.plan, user=self.student, date=first.planned_date, title="本人自主任务",
        )
        url = reverse("training:my_training")
        self.client.force_login(self.student)
        response = self.client.get(url)
        self.assertContains(response, "选手视图")
        self.assertContains(response, "选手甲的任务")
        self.assertContains(response, "进行中")
        self.assertContains(response, "本人自主任务")
        self.assertNotContains(response, "选手乙的任务")
        self.assertContains(response, reverse("training:execution_detail", args=[first.executions.get().pk]))
        self.assertNotContains(self.client.get(url, {"date": "2026-01-02"}), "选手甲的任务")
        self.assertContains(self.client.get(url, {"date": "2026-01-02", "scope": "all"}), "选手甲的任务")

        self.client.force_login(self.student2)
        response = self.client.get(url)
        self.assertContains(response, second.title)
        self.assertNotContains(response, first.title)
        self.assertNotContains(response, "本人自主任务")
        second.executions.update(revoked_at=timezone.now())
        self.assertNotContains(self.client.get(url), second.title)

    def test_coach_sees_current_responsibility_and_allowed_execution_summary(self):
        morning = self.task(title="上午负责")
        afternoon = self.plan.schedule_days.get(date=morning.planned_date).slots.get(period="afternoon")
        afternoon.coaches.add(self.other)
        TrainingTask.objects.create(
            training_plan=self.plan, schedule_slot=afternoon, planned_date=morning.planned_date,
            title="下午负责", status="published", created_by=self.other,
        )
        TrainingTask.objects.create(
            training_plan=self.plan, schedule_slot=self.slot, planned_date=morning.planned_date,
            title="草稿任务", created_by=self.coach,
        )
        legacy = TrainingTask.objects.create(
            training_plan=self.plan, planned_date=morning.planned_date,
            title="历史教练任务", status="published", created_by=self.coach,
        )
        TrainingTaskCoach.objects.create(training_task=legacy, user=self.coach)
        url = reverse("training:my_training")
        self.client.force_login(self.coach)
        response = self.client.get(url)
        self.assertContains(response, "教练视图")
        self.assertContains(response, "上午负责")
        self.assertContains(response, "未开始 2 人")
        self.assertContains(response, "未标注时段")
        self.assertContains(response, "历史教练任务")
        self.assertNotContains(response, "下午负责")
        self.assertNotContains(response, "草稿任务")
        self.coach.user_permissions.remove(self.coach.user_permissions.get(codename="view_taskexecution"))
        self.assertNotContains(self.client.get(url), "未开始 2 人")

        self.slot.coaches.set([self.other])
        self.assertNotContains(self.client.get(url), "上午负责")
        self.client.force_login(self.other)
        response = self.client.get(url)
        self.assertContains(response, "上午负责")
        self.assertContains(response, "下午负责")

    def test_dual_membership_prefers_competitor_view(self):
        task = self.task()
        self.slot.coaches.add(self.student)
        self.client.force_login(self.student)
        response = self.client.get(reverse("training:my_training"))
        self.assertContains(response, "选手视图")
        self.assertContains(response, reverse("training:execution_detail", args=[task.executions.get(user=self.student).pk]))

    def test_public_screen_requires_explicit_listing_and_current_publication(self):
        task = self.task(title="公开任务标题", description="内部任务正文")
        self.slot.day.duty_coaches.set([self.other])
        self.coach.username = "private-board-coach-account"
        self.coach.save(update_fields=["username"])
        url = reverse("training:board")
        self.assertContains(self.client.get(url), "今日暂无公开训练任务")
        listing = TrainingBoardPlan.objects.create(training_plan=self.plan)
        other_plan = type(self.plan).objects.create(
            training_cycle=self.cycle_obj, title="另一份上屏计划", start_date=self.plan.start_date,
            end_date=self.plan.end_date, published_at=timezone.now(), schedule_published_at=timezone.now(),
            created_by=self.admin,
        )
        TrainingBoardPlan.objects.create(training_plan=other_plan)
        other_day = other_plan.schedule_days.create(date=task.planned_date)
        other_slot = other_day.slots.create(period="afternoon", kind="comprehensive")
        TrainingTask.objects.create(
            training_plan=other_plan, schedule_slot=other_slot, planned_date=task.planned_date,
            status="published", title="第二份计划任务", created_by=self.admin,
        )
        for params in ({}, {"fragment": "1"}):
            response = self.client.get(url, params)
            self.assertContains(response, task.title)
            self.assertContains(response, "第二份计划任务")
            self.assertContains(response, "专业领域")
            self.assertContains(response, self.linux.name)
            self.assertContains(response, "综合")
            self.assertContains(response, "负责教练")
            self.assertContains(response, self.coach.first_name)
            self.assertContains(response, "值班教练")
            self.assertContains(response, self.other.first_name)
            self.assertNotContains(response, self.coach.username)
            self.assertNotContains(response, "内部任务正文")
            self.assertNotContains(response, self.student.first_name)
            self.assertNotContains(response, reverse("training:task_detail", args=[task.pk]))
            self.assertIn("no-store", response.headers["Cache-Control"])

        TrainingTask.objects.filter(pk=task.pk).update(status="draft")
        response = self.client.get(url)
        self.assertNotContains(response, task.title)
        self.assertNotContains(response, self.coach.first_name)
        self.assertNotContains(response, self.other.first_name)
        TrainingTask.objects.filter(pk=task.pk).update(status="published")
        type(self.plan).objects.filter(pk=self.plan.pk).update(schedule_published_at=None)
        self.assertNotContains(self.client.get(url), task.title)
        type(self.plan).objects.filter(pk=self.plan.pk).update(schedule_published_at=timezone.now())
        with patch("django.utils.timezone.now", return_value=datetime(2026, 1, 1, 16, tzinfo=utc.utc)):
            self.assertContains(self.client.get(url, {"fragment": "1"}), "2026年1月2日")
            self.assertNotContains(self.client.get(url), task.title)
        listing.delete()
        self.assertNotContains(self.client.get(url), task.title)

    def test_all_coaches_are_displayed_without_expanding_the_roster(self):
        task = self.task(title="全体教练负责的任务")
        self.slot.coaches_all = True
        self.slot.save(update_fields=["coaches_all"])
        day = self.slot.day
        day.duty_all = True
        day.save(update_fields=["duty_all"])
        day.duty_coaches.set([self.other])
        TrainingBoardPlan.objects.create(training_plan=self.plan)

        response = self.client.get(reverse("training:board"), {"fragment": "1"})
        self.assertContains(response, "· 全体", count=2)
        self.assertNotContains(response, self.coach.first_name)
        self.assertNotContains(response, self.other.first_name)

        self.client.force_login(self.admin)
        response = self.client.get(reverse("training:plan_detail", args=[self.plan.pk]))
        self.assertContains(response, '<p class="text-sm">全体</p>', html=True)
        response = self.client.get(reverse("training:task_detail", args=[task.pk]))
        self.assertContains(response, '<h3 class="card-title">教练</h3><span>全体</span>', html=True)

    def test_board_listing_uses_published_plan_detail_and_superuser_permission(self):
        detail = reverse("training:plan_detail", args=[self.plan.pk])
        url = reverse("training:plan_board_listing", args=[self.plan.pk])
        self.client.force_login(self.coach)
        self.assertNotContains(self.client.get(detail), "加入大屏")
        self.assertEqual(self.client.post(url, {"action": "add"}).status_code, 403)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertContains(self.client.get(detail), "加入大屏")
        self.assertRedirects(self.client.post(url, {"action": "add"}), detail, fetch_redirect_response=False)
        self.client.post(url, {"action": "add"})
        self.assertEqual(TrainingBoardPlan.objects.filter(training_plan=self.plan).count(), 1)
        self.assertContains(self.client.get(detail), "移出大屏")
        self.client.post(url, {"action": "remove"})
        self.assertFalse(TrainingBoardPlan.objects.filter(training_plan=self.plan).exists())

        type(self.plan).objects.filter(pk=self.plan.pk).update(published_at=None, schedule_published_at=None)
        self.assertNotContains(self.client.get(detail), "加入大屏")
        response = self.client.post(url, {"action": "add"}, follow=True)
        self.assertContains(response, "只有已发布的训练计划可设置上屏")
        self.assertFalse(TrainingBoardPlan.objects.filter(training_plan=self.plan).exists())

    def test_withdrawing_plan_removes_listing_until_explicitly_added_again(self):
        type(self.plan).objects.filter(pk=self.plan.pk).update(schedule_published_at=None)
        TrainingBoardPlan.objects.create(training_plan=self.plan)
        self.client.force_login(self.admin)
        url = reverse("training:withdraw_publication", args=[self.plan.pk, "plan"])
        response = self.client.post(url, {"reason": "调整训练计划"})
        self.assertTrue(response.context["token"])
        self.assertEqual(self.client.post(url, {"token": response.context["token"]}).status_code, 302)
        self.assertFalse(TrainingBoardPlan.objects.filter(training_plan=self.plan).exists())

        url = reverse("training:plan_publish", args=[self.plan.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.published_at)
        self.assertFalse(TrainingBoardPlan.objects.filter(training_plan=self.plan).exists())
