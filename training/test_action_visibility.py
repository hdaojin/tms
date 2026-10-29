from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.test import TestCase
from django.urls import reverse

from training.models import TrainingPlan, TrainingTask, TrainingTaskDomain, TaskExecution, TrainingCycleMember
from standards.models import TechnicalDomainGroupScope
from training.tests import TrainingFixtureMixin


class TrainingActionVisibilityTests(TrainingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user("action-viewer")
        self.owner = get_user_model().objects.create_user("action-owner")
        self.c = self.cycle()
        self.bind(self.c)
        self.plan = TrainingPlan.objects.create(
            training_cycle=self.c,
            title="计划",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            created_by=self.owner,
        )
        self.task = TrainingTask.objects.create(
            training_plan=self.plan,
            title="任务",
            planned_date=date(2026, 1, 10),
            requirements="任务要求",
            created_by=self.owner,
        )
        TrainingTaskDomain.objects.create(training_task=self.task, technical_domain=self.linux, role="primary")
        TrainingCycleMember.objects.create(training_cycle=self.c, user=self.user, role="competitor")
        TaskExecution.objects.create(training_task=self.task, user=self.user)
        self.grant(
            "view_trainingcycle",
            "view_trainingtask",
            "change_trainingtask",
            "view_taskexecution",
            "change_taskexecution",
        )
        self.client.force_login(self.user)

    def grant(self, *codes):
        self.user.user_permissions.add(
            *Permission.objects.filter(content_type__app_label="training", codename__in=codes)
        )

    def test_no_add_permission_hides_entry_and_backend_remains_forbidden(self):
        response = self.client.get(reverse("training:cycle_list"))
        self.assertNotContains(response, reverse("training:cycle_create"))
        self.assertEqual(self.client.get(reverse("training:cycle_create")).status_code, 403)
        self.grant("add_trainingcycle")
        self.assertContains(self.client.get(reverse("training:cycle_list")), reverse("training:cycle_create"))

    def test_task_edit_hidden_when_visible_through_execution_but_not_manageable(self):
        url = reverse("training:task_edit", args=[self.task.pk])
        self.assertNotContains(self.client.get(reverse("training:task_list")), url)
        self.assertNotContains(self.client.get(reverse("training:task_detail", args=[self.task.pk])), url)
        self.assertEqual(self.client.get(url).status_code, 404)
        group = Group.objects.create(name="有领域的任务维护")
        group.permissions.add(
            Permission.objects.get(content_type__app_label="training", codename="change_trainingtask")
        )
        TechnicalDomainGroupScope.objects.create(group=group, technical_domain=self.linux)
        self.user.groups.add(group)
        self.assertContains(self.client.get(reverse("training:task_list")), url)
        self.assertContains(self.client.get(reverse("training:task_detail", args=[self.task.pk])), url)

    def test_execution_edit_link_only_for_own_execution(self):
        other_cycle = self.cycle(code="OTHER")
        self.bind(other_cycle)
        TrainingCycleMember.objects.create(training_cycle=other_cycle, user=self.owner, role="competitor")
        TrainingCycleMember.objects.create(training_cycle=other_cycle, user=self.user, role="coach")
        plan = TrainingPlan.objects.create(
            training_cycle=other_cycle,
            title="另一计划",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            created_by=self.owner,
        )
        task = TrainingTask.objects.create(
            training_plan=plan,
            title="另一任务",
            planned_date=date(2026, 1, 10),
            requirements="要求",
            created_by=self.owner,
        )
        task.coach_links.create(user=self.user, role="primary")
        other = TaskExecution.objects.create(training_task=task, user=self.owner)
        response = self.client.get(reverse("training:execution_list"))
        mine = TaskExecution.objects.get(training_task=self.task, user=self.user)
        self.assertContains(response, reverse("training:execution_edit", args=[mine.pk]))
        self.assertNotContains(response, reverse("training:execution_edit", args=[other.pk]))
        self.assertContains(response, reverse("training:execution_detail", args=[other.pk]))
